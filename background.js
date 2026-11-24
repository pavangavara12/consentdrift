// ConsentDrift Chrome Extension Background Service Worker (Manifest V3)

const BACKEND_URL = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "send_selection_evidence",
      title: "Send selection to ConsentDrift as evidence",
      contexts: ["selection"]
    });

    chrome.contextMenus.create({
      id: "save_page_baseline",
      title: "Save this page as consent baseline",
      contexts: ["page"]
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "send_selection_evidence") {
    const selectedText = info.selectionText ? info.selectionText.trim() : "";
    if (!selectedText) return;

    await chrome.storage.local.set({
      pending_evidence: {
        content: selectedText,
        source: tab && tab.url ? tab.url : "",
        title: tab && tab.title ? `Evidence: ${tab.title.slice(0, 60)}` : "Extracted Web Evidence",
        timestamp: Date.now()
      }
    });

    chrome.action.setBadgeText({ text: "NEW" });
    chrome.action.setBadgeBackgroundColor({ color: "#2563EB" });
  }

  if (info.menuItemId === "save_page_baseline") {
    if (!tab || !tab.id) return;

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          return {
            title: document.title || "Web Baseline",
            url: window.location.href,
            text: document.body ? document.body.innerText.trim().slice(0, 20000) : ""
          };
        }
      });

      if (!results || !results[0] || !results[0].result) {
        throw new Error("Unable to read page text.");
      }

      const { title, url, text } = results[0].result;
      let organisation = "Web Service";
      try {
        organisation = new URL(url).hostname.replace(/^www\./, "");
      } catch (err) {
        // fallback
      }

      const response = await fetch(`${BACKEND_URL}/api/consents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organisation: organisation,
          service_name: title.slice(0, 100),
          original_purpose: text || `Captured privacy disclosure from ${url}`,
          data_categories: [],
          source_type: "official_text"
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      chrome.action.setBadgeText({ text: "SAVED" });
      chrome.action.setBadgeBackgroundColor({ color: "#16A34A" });
      setTimeout(() => {
        chrome.action.setBadgeText({ text: "" });
      }, 3500);
    } catch (error) {
      console.error("Failed to save baseline consent:", error);
      chrome.action.setBadgeText({ text: "ERR" });
      chrome.action.setBadgeBackgroundColor({ color: "#DC2626" });
      setTimeout(() => {
        chrome.action.setBadgeText({ text: "" });
      }, 3500);
    }
  }
});
