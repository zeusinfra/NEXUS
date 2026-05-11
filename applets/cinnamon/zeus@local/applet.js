const Applet = imports.ui.applet;
const Mainloop = imports.mainloop;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Settings = imports.ui.settings;
const Soup = imports.gi.Soup;
const ByteArray = imports.byteArray;

const APPLET_UUID = 'zeus@local';
const APPLET_VERSION = '1.0.4';
const DEFAULT_BACKEND = 'http://127.0.0.1:8080';
const PROJECT_ROOT = '__ZEUS_PROJECT_ROOT__';
const POLL_SECONDS = 10;

function _projectRoot() {
    if (PROJECT_ROOT.indexOf('__ZEUS_') !== 0) {
        return PROJECT_ROOT;
    }
    return GLib.build_filenamev([GLib.get_home_dir(), 'Documentos', 'ZEUS_SYSTEM']);
}

function _truncate(text, limit) {
    text = String(text || '').replace(/\s+/g, ' ').trim();
    if (text.length <= limit) {
        return text;
    }
    return text.slice(0, limit - 1) + '...';
}

class ZeusApplet extends Applet.TextIconApplet {
    constructor(orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);

        this._backendUrl = DEFAULT_BACKEND;
        this._pollTimer = null;
        this._online = false;
        this._settings = null;

        this.set_applet_icon_symbolic_name('network-offline-symbolic');
        this.set_applet_label('NEXUS');
        this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ': verificando backend...');

        this._initSettings(instanceId);

        try {
            this._soupSession = new Soup.Session();
            this._soupSession.timeout = 4;
        } catch (e) {
            // Fallback for older Soup
            this._soupSession = new Soup.SessionAsync();
            this._soupSession.timeout = 4;
        }

        this._refreshStatus();
        this._pollTimer = Mainloop.timeout_add_seconds(POLL_SECONDS, () => {
            this._refreshStatus();
            return true;
        });
    }

    on_applet_clicked() {
        if (this._online) {
            this._openChat();
        } else {
            this._startBackend();
        }
        this._refreshStatus();
    }

    on_applet_removed_from_panel() {
        if (this._pollTimer) {
            Mainloop.source_remove(this._pollTimer);
            this._pollTimer = null;
        }
    }

    _initSettings(instanceId) {
        try {
            this._settings = new Settings.AppletSettings(this, APPLET_UUID, instanceId);
            this._settings.bindProperty(
                Settings.BindingDirection.IN,
                'backend-url',
                '_backendUrl',
                () => this._refreshStatus(),
                null
            );
        } catch (e) {
            this._backendUrl = DEFAULT_BACKEND;
        }
    }

    _httpRequest(url, callback) {
        let msg = Soup.Message.new('GET', url);
        if (!msg) {
            callback(false, '', 'Invalid URL');
            return;
        }

        if (this._soupSession.send_and_read_async) {
            // Soup 3.0
            this._soupSession.send_and_read_async(msg, GLib.PRIORITY_DEFAULT, null, (session, result) => {
                try {
                    let bytes = session.send_and_read_finish(result);
                    let ok = (msg.get_status() === Soup.Status.OK);
                    let body = '';
                    if (bytes) {
                        try {
                            body = new TextDecoder().decode(bytes.get_data());
                        } catch (e) {
                            body = ByteArray.toString(bytes.get_data());
                        }
                    }
                    callback(ok, body, '');
                } catch (e) {
                    callback(false, '', String(e));
                }
            });
        } else {
            // Soup 2.4
            this._soupSession.queue_message(msg, (session, message) => {
                let ok = (message.status_code === Soup.Status.OK);
                let body = message.response_body ? message.response_body.data : '';
                callback(ok, body, '');
            });
        }
    }

    _refreshStatus() {
        this._httpRequest(this._backendUrl + '/api/applet/status', (ok, stdout, stderr) => {
            if (!ok) {
                this._online = false;
                this.set_applet_icon_symbolic_name('network-offline-symbolic');
                this.set_applet_label('NEXUS');
                this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ' offline. Clique para iniciar backend. ' + _truncate(stderr || '', 90));
                return;
            }

            try {
                const data = JSON.parse(stdout);
                const llm = data.llm || {};
                const provider = llm.provider || 'llm';
                const model = llm.model || 'modelo';
                const configured = !!llm.configured;
                this._online = true;
                this.set_applet_icon_symbolic_name(configured ? 'network-server-symbolic' : 'dialog-warning-symbolic');
                this.set_applet_label('NEXUS');
                this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ' online: ' + provider + ' / ' + model + '. Clique para abrir chat.');
            } catch (e) {
                this._online = false;
                this.set_applet_icon_symbolic_name('dialog-warning-symbolic');
                this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ': resposta invalida do backend.');
            }
        });
    }

    _openHud() {
        Gio.AppInfo.launch_default_for_uri(this._backendUrl, null);
    }

    _openChat() {
        const root = _projectRoot();
        const chat = GLib.build_filenamev([root, 'bin', 'zeus-chat']);
        try {
            GLib.spawn_async(
                root,
                [chat, this._backendUrl],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );
        } catch (e) {
            this.set_applet_icon_symbolic_name('dialog-error-symbolic');
            this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ': erro ao abrir chat: ' + _truncate(String(e), 120));
        }
    }

    _startBackend() {
        const root = _projectRoot();
        const launcher = GLib.build_filenamev([root, 'bin', 'zeus']);
        try {
            GLib.spawn_async(
                root,
                [launcher, 'ensure-server'],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );
            this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ': iniciando backend...');
        } catch (e) {
            this.set_applet_icon_symbolic_name('dialog-error-symbolic');
            this.set_applet_tooltip('NEXUS ' + APPLET_VERSION + ': erro ao iniciar backend: ' + _truncate(String(e), 120));
        }
        Mainloop.timeout_add_seconds(4, () => {
            this._refreshStatus();
            return false;
        });
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new ZeusApplet(orientation, panelHeight, instanceId);
}
