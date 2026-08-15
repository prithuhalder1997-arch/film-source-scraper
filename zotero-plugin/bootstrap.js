// Bootstrap entry point for Zotero 7. Loads the plugin logic into each window.

var chromeHandle;

function log(msg) { Zotero.debug("[FilmScraper] " + msg); }

async function install() { log("installed"); }
async function uninstall() { log("uninstalled"); }

async function startup({ id, version, rootURI }) {
  log("starting " + version);

  // register chrome:// mapping so we can load content/*
  const aomStartup = Components.classes[
    "@mozilla.org/addons/addon-manager-startup;1"
  ].getService(Components.interfaces.amIAddonManagerStartup);
  const manifestURI = Services.io.newURI(rootURI + "manifest.json");
  chromeHandle = aomStartup.registerChrome(manifestURI, [
    ["content", "filmscraper", rootURI + "content/"],
  ]);

  // load main logic
  Services.scriptloader.loadSubScript(
    rootURI + "content/scraper.js", { Zotero, rootURI }
  );

  // wire into all existing + future windows
  FilmScraper.init({ id, version, rootURI });
  FilmScraper.addToAllWindows();
}

function shutdown() {
  log("shutting down");
  if (typeof FilmScraper !== "undefined") {
    FilmScraper.removeFromAllWindows();
  }
  if (chromeHandle) { chromeHandle.destruct(); chromeHandle = null; }
}

function onMainWindowLoad({ window }) {
  if (typeof FilmScraper !== "undefined") FilmScraper.addToWindow(window);
}
function onMainWindowUnload({ window }) {
  if (typeof FilmScraper !== "undefined") FilmScraper.removeFromWindow(window);
}
