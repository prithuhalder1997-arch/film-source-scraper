// Main plugin logic. Adds a right-click item to collections and drives the
// local Capture Engine. Contains NO scraping logic itself — that all lives in
// the Python engine. This file is purely the button + progress UI + polling.

var FilmScraper = {
  id: null,
  version: null,
  rootURI: null,
  ENGINE: "http://127.0.0.1:23200",
  _menuIds: [],

  init({ id, version, rootURI }) {
    this.id = id; this.version = version; this.rootURI = rootURI;
  },

  // ---- window plumbing ----------------------------------------------------
  addToAllWindows() {
    for (const win of Zotero.getMainWindows()) this.addToWindow(win);
  },
  removeFromAllWindows() {
    for (const win of Zotero.getMainWindows()) this.removeFromWindow(win);
  },

  addToWindow(window) {
    const doc = window.document;
    // Zotero's collection context menu id is "zotero-collectionmenu"
    const menu = doc.getElementById("zotero-collectionmenu");
    if (!menu) return;

    const item = doc.createXULElement("menuitem");
    item.id = "filmscraper-menuitem";
    item.setAttribute("label", "Scrape film sources for this collection");
    item.addEventListener("command", () => this.onScrapeClicked(window));
    menu.appendChild(item);
    this._menuIds.push(item.id);
  },

  removeFromWindow(window) {
    const doc = window.document;
    for (const id of this._menuIds) {
      const el = doc.getElementById(id);
      if (el) el.remove();
    }
  },

  // ---- engine communication ----------------------------------------------
  async engineHealth() {
    try {
      const r = await fetch(this.ENGINE + "/health", { method: "GET" });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) {
      return null;   // engine not running
    }
  },

  async onScrapeClicked(window) {
    // 1. which collection is selected?
    const zp = Zotero.getActiveZoteroPane();
    const collection = zp.getSelectedCollection();
    if (!collection) {
      window.alert("Select a collection first.");
      return;
    }
    const filmTitle = collection.name;   // collection name = film title

    // 2. is the engine up?
    const health = await this.engineHealth();
    if (!health) {
      this.showEngineMissing(window);
      return;
    }
    if (!health.zotero_up) {
      window.alert("The engine is running but can't reach Zotero's connector. " +
                   "Make sure Zotero is open (it is) and try again.");
      return;
    }

    // 3. kick off the job
    const progress = new Zotero.ProgressWindow({ closeOnClick: false });
    progress.changeHeadline("Scraping sources: " + filmTitle);
    const line = new progress.ItemProgress(null, "Starting…");
    progress.show();

    let job;
    try {
      const r = await fetch(this.ENGINE + "/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          film: { title: filmTitle },
          collectionKey: collection.key,
          hits_per_source: 3,
          use_wayback: true,
        }),
      });
      job = await r.json();
    } catch (e) {
      line.setText("Failed to reach engine: " + e);
      return;
    }

    // 4. poll for progress
    this.pollJob(job.job_id, progress, line);
  },

  async pollJob(jobId, progress, line) {
    const tick = async () => {
      let s;
      try {
        const r = await fetch(this.ENGINE + "/status/" + jobId);
        s = await r.json();
      } catch (e) {
        line.setText("Lost contact with engine.");
        return;
      }
      const last = s.log && s.log.length ? s.log[s.log.length - 1] : "working…";
      line.setText(last);
      if (s.done) {
        if (s.error) {
          line.setError();
          line.setText("Error: " + s.error);
        } else {
          line.setProgress(100);
          line.setText("Done — sources filed into the collection.");
        }
        progress.startCloseTimer(6000);
        return;
      }
      setTimeout(tick, 1500);
    };
    tick();
  },

  showEngineMissing(window) {
    const ps = Services.prompt;
    const url = "https://github.com/prithuhalder1997-arch/film-source-scraper/releases";
    const btn = ps.confirmEx(
      window,
      "Capture Engine not running",
      "This plugin needs the local Capture Engine app to be open.\n\n" +
      "If you haven't installed it yet, download it once and double-click to " +
      "start it. Leave it running in the background while you scrape.",
      ps.BUTTON_POS_0 * ps.BUTTON_TITLE_IS_STRING +
      ps.BUTTON_POS_1 * ps.BUTTON_TITLE_CANCEL,
      "Open download page", null, null, null, {}
    );
    if (btn === 0) Zotero.launchURL(url);
  },
};
