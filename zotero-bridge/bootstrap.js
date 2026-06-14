var PaperHunterBridge = {
  version: "0.2.2",
  protocolVersion: 1,
  pairingToken: "__PAPERHUNTER_BRIDGE_TOKEN__",
  managedNoteMarker: "PaperHunter 同步结果",
  managedNoteAttribute: 'data-paperhunter-marker="sync-result"',
  tagPrefix: "paperhunter",
  allowedAttachmentExtensions: [".md", ".markdown"],
  supportedCapabilities: {
    canUpsertManagedNote: true,
    canApplyPaperHunterTags: true,
    canLinkMarkdownAttachment: true,
    preserveUserContent: true,
    requiresPairingToken: true,
    canVerifyPairingToken: true,
  },

  install() {},
  uninstall() {},

  startup() {
    this.registerEndpoints();
    Zotero.debug("PaperHunter Zotero Bridge started");
  },

  shutdown() {
    Zotero.debug("PaperHunter Zotero Bridge stopped");
  },

  registerEndpoints() {
    if (!Zotero.Server || !Zotero.Server.Endpoints) {
      throw new Error("Zotero HTTP server endpoint API is unavailable.");
    }
    if (!Zotero.Server.Connector) {
      Zotero.Server.Connector = {};
    }

    Zotero.Server.Connector.PaperHunterPing = function () {};
    Zotero.Server.Endpoints["/paperhunter/ping"] = Zotero.Server.Connector.PaperHunterPing;
    Zotero.Server.Connector.PaperHunterPing.prototype = {
      supportedMethods: ["GET"],
      supportedDataTypes: ["*"],
      permitBookmarklet: true,
      async init(_requestData) {
        return [200, "application/json", JSON.stringify({
          ok: true,
          name: "PaperHunter Zotero Bridge",
          version: PaperHunterBridge.version,
          protocolVersion: PaperHunterBridge.protocolVersion,
          policy: PaperHunterBridge.policy(),
          capabilities: PaperHunterBridge.capabilities(),
        })];
      },
    };

    Zotero.Server.Connector.PaperHunterPairingCheck = function () {};
    Zotero.Server.Endpoints["/paperhunter/pairing-check"] = Zotero.Server.Connector.PaperHunterPairingCheck;
    Zotero.Server.Connector.PaperHunterPairingCheck.prototype = {
      supportedMethods: ["POST"],
      supportedDataTypes: ["application/json"],
      permitBookmarklet: true,
      async init(requestData) {
        try {
          PaperHunterBridge.assertLocalRequest(requestData);
          PaperHunterBridge.assertPaired(requestData.data || {});
          return [200, "application/json", JSON.stringify({
            ok: true,
            tokenAccepted: true,
            version: PaperHunterBridge.version,
            protocolVersion: PaperHunterBridge.protocolVersion,
          })];
        } catch (error) {
          Zotero.debug(`PaperHunter Bridge pairing check failed: ${error}`);
          return [401, "application/json", JSON.stringify({ ok: false, error: String(error && error.message || error) })];
        }
      },
    };

    Zotero.Server.Connector.PaperHunterSync = function () {};
    Zotero.Server.Endpoints["/paperhunter/sync"] = Zotero.Server.Connector.PaperHunterSync;
    Zotero.Server.Connector.PaperHunterSync.prototype = {
      supportedMethods: ["POST"],
      supportedDataTypes: ["application/json"],
      permitBookmarklet: true,
      async init(requestData) {
        try {
          PaperHunterBridge.assertLocalRequest(requestData);
          const payload = requestData.data || {};
          const result = await PaperHunterBridge.syncItem(payload);
          return [200, "application/json", JSON.stringify({ ok: true, ...result })];
        } catch (error) {
          Zotero.debug(`PaperHunter Bridge sync failed: ${error}`);
          return [400, "application/json", JSON.stringify({ ok: false, error: String(error && error.message || error) })];
        }
      },
    };
  },

  async syncItem(payload) {
    this.assertPaired(payload);

    const itemKey = String(payload.itemKey || "").trim();
    if (!itemKey) {
      throw new Error("Missing Zotero itemKey");
    }

    const item = await this.findItem(itemKey);
    if (!item) {
      throw new Error(`Zotero item not found: ${itemKey}`);
    }

    const noteHtml = String(payload.noteHtml || "");
    if (noteHtml && !noteHtml.includes(this.managedNoteMarker)) {
      throw new Error("PaperHunter note marker is missing");
    }
    const noteID = await this.upsertNote(item, noteHtml);
    const tags = this.cleanTags(payload.tags);
    await this.addTags(item, tags);

    const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
    const allowedRoots = this.cleanAllowedRoots(payload.allowedAttachmentRoots);
    const attachmentIDs = [];
    for (const attachmentPath of attachments) {
      const attachmentID = await this.linkAttachment(item, String(attachmentPath || ""), allowedRoots);
      if (attachmentID) {
        attachmentIDs.push(attachmentID);
      }
    }

    await item.saveTx();
    return {
      itemKey,
      itemID: item.id,
      noteID,
      tags,
      attachments: attachmentIDs.length,
      policy: this.policy(),
      capabilities: this.capabilities(),
    };
  },

  capabilities() {
    return { ...this.supportedCapabilities };
  },

  policy() {
    return {
      tagPrefix: this.tagPrefix,
      noteMode: "upsert-managed-note-only",
      attachmentMode: "link-translated-markdown-only",
      preserveUserContent: true,
    };
  },

  assertPaired(payload) {
    if (Number(payload.protocolVersion || 0) !== this.protocolVersion) {
      throw new Error(`Unsupported PaperHunter bridge protocol: ${payload.protocolVersion || "missing"}`);
    }
    if (String(payload.client || "") !== "PaperHunter") {
      throw new Error("Unsupported bridge client");
    }
    if (String(payload.pairingToken || "") !== this.pairingToken) {
      throw new Error("PaperHunter Bridge pairing token is invalid");
    }
  },

  assertLocalRequest(requestData) {
    const remoteAddress = String(
      requestData && (
        requestData.remoteAddress
        || requestData.remoteHost
        || requestData.host
        || ""
      ) || ""
    ).replace(/^::ffff:/, "");
    if (remoteAddress && !["127.0.0.1", "::1", "localhost"].includes(remoteAddress)) {
      throw new Error("PaperHunter Bridge only accepts local requests");
    }
  },

  cleanAllowedRoots(roots) {
    if (!Array.isArray(roots)) {
      return [];
    }
    return roots
      .map((root) => this.normalizePath(root))
      .filter((root) => root.length > 0);
  },

  cleanTags(tags) {
    if (!Array.isArray(tags)) {
      return [];
    }
    const clean = [];
    for (const tag of tags) {
      const value = String(tag || "").trim();
      if (value === this.tagPrefix || value.startsWith(`${this.tagPrefix}:`)) {
        clean.push(value);
      }
    }
    return [...new Set(clean)].sort();
  },

  async findItem(itemKey) {
    const libraries = Zotero.Libraries.getAll();
    for (const library of libraries) {
      const item = await Zotero.Items.getByLibraryAndKeyAsync(library.libraryID, itemKey);
      if (item) {
        return item;
      }
    }
    return null;
  },

  async upsertNote(parentItem, noteHtml) {
    if (!noteHtml.trim()) {
      return null;
    }

    const children = await parentItem.getNotes();
    for (const noteID of children) {
      const note = await Zotero.Items.getAsync(noteID);
      if (!note || !note.isNote()) {
        continue;
      }
      const existingNote = note.getNote() || "";
      if (this.isManagedNote(existingNote)) {
        note.setNote(noteHtml);
        await note.saveTx();
        return note.id;
      }
    }

    const note = new Zotero.Item("note");
    note.libraryID = parentItem.libraryID;
    note.parentID = parentItem.id;
    note.setNote(noteHtml);
    await note.saveTx();
    return note.id;
  },

  isManagedNote(noteHtml) {
    const note = String(noteHtml || "");
    return note.includes(this.managedNoteMarker) || note.includes(this.managedNoteAttribute);
  },

  async addTags(item, tags) {
    for (const tag of tags) {
      const cleanTag = String(tag || "").trim();
      if (cleanTag) {
        item.addTag(cleanTag);
      }
    }
  },

  async linkAttachment(parentItem, attachmentPath, allowedRoots) {
    if (!attachmentPath.trim()) {
      return null;
    }

    const normalizedPath = await this.normalizePath(attachmentPath);
    if (!this.allowedAttachmentExtensions.some((suffix) => normalizedPath.endsWith(suffix))) {
      throw new Error("PaperHunter Bridge only links translated Markdown attachments");
    }
    if (!Array.isArray(allowedRoots) || !allowedRoots.length) {
      throw new Error("PaperHunter Bridge requires allowed attachment roots");
    }
    if (!allowedRoots.some((root) => normalizedPath === root || normalizedPath.startsWith(`${root}/`))) {
      throw new Error("PaperHunter Bridge only links attachments inside PaperHunter translated output");
    }

    if (!await IOUtils.exists(attachmentPath)) {
      throw new Error(`Attachment file does not exist: ${attachmentPath}`);
    }

    const childIDs = await parentItem.getAttachments();
    for (const childID of childIDs) {
      const child = await Zotero.Items.getAsync(childID);
      if (!child || !child.isAttachment()) {
        continue;
      }
      const childPath = child.getFilePath && child.getFilePath();
      if (childPath && await this.normalizePath(childPath) === normalizedPath) {
        return child.id;
      }
    }

    const attachment = await Zotero.Attachments.linkFromFile({
      file: attachmentPath,
      parentItemID: parentItem.id,
      title: "PaperHunter full-text translation",
      contentType: "text/markdown",
    });
    return attachment && attachment.id;
  },

  async normalizePath(path) {
    return String(path || "")
      .replace(/\\/g, "/")
      .replace(/\/+/g, "/")
      .replace(/^([a-z]):/i, "$1")
      .toLowerCase();
  },
};

function install() {
  return PaperHunterBridge.install();
}

function uninstall() {
  return PaperHunterBridge.uninstall();
}

function startup(data, reason) {
  return PaperHunterBridge.startup(data, reason);
}

function shutdown(data, reason) {
  return PaperHunterBridge.shutdown(data, reason);
}
