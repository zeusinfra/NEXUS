const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const Mainloop = imports.mainloop;
const St = imports.gi.St;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;

const APPLET_UUID = 'zeus@local';
const DEFAULT_BACKEND = 'http://127.0.0.1:8080';
const PROJECT_ROOT = '__ZEUS_PROJECT_ROOT__';
const POLL_SECONDS = 10;
const MAX_MESSAGES = 8;

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
    return text.slice(0, limit - 1) + '…';
}

class ZeusApplet extends Applet.TextIconApplet {
    constructor(orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);

        this._backendUrl = DEFAULT_BACKEND;
        this._messages = [];
        this._pollTimer = null;
        this._busy = false;

        this.set_applet_icon_symbolic_name('network-server-symbolic');
        this.set_applet_label('ZEUS');
        this.set_applet_tooltip('ZEUS: conectando...');

        this._menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this._menuManager.addMenu(this.menu);

        this._buildMenu();
        this._refreshStatus();
        this._pollTimer = Mainloop.timeout_add_seconds(POLL_SECONDS, () => {
            this._refreshStatus();
            return true;
        });
    }

    on_applet_clicked() {
        this.menu.toggle();
        this._refreshStatus();
    }

    on_applet_removed_from_panel() {
        if (this._pollTimer) {
            Mainloop.source_remove(this._pollTimer);
            this._pollTimer = null;
        }
    }

    _buildMenu() {
        this.menu.removeAll();

        this._statusItem = new PopupMenu.PopupMenuItem('ZEUS: verificando...', { reactive: false });
        this._statusItem.label.add_style_class_name('zeus-applet-title');
        this.menu.addMenuItem(this._statusItem);

        this._detailItem = new PopupMenu.PopupMenuItem('Aguardando backend local', { reactive: false });
        this._detailItem.label.add_style_class_name('zeus-applet-muted');
        this.menu.addMenuItem(this._detailItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._historySection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._historySection);
        this._renderHistory();

        const inputItem = new PopupMenu.PopupBaseMenuItem({ reactive: false });
        this._entry = new St.Entry({
            name: 'zeus-chat-entry',
            hint_text: 'Mensagem para o ZEUS',
            can_focus: true,
            track_hover: true,
            style_class: 'zeus-chat-entry'
        });
        this._entry.clutter_text.connect('activate', () => this._sendChat());
        inputItem.addActor(this._entry, { expand: true });
        this.menu.addMenuItem(inputItem);

        const sendItem = new PopupMenu.PopupMenuItem('Enviar mensagem');
        sendItem.connect('activate', () => this._sendChat());
        this.menu.addMenuItem(sendItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const voiceItem = new PopupMenu.PopupMenuItem('Iniciar voz');
        voiceItem.connect('activate', () => this._startVoice());
        this.menu.addMenuItem(voiceItem);

        const visionItem = new PopupMenu.PopupMenuItem('Analisar tela');
        visionItem.connect('activate', () => this._startVision());
        this.menu.addMenuItem(visionItem);

        const hudItem = new PopupMenu.PopupMenuItem('Abrir HUD');
        hudItem.connect('activate', () => this._openHud());
        this.menu.addMenuItem(hudItem);

        const backendItem = new PopupMenu.PopupMenuItem('Iniciar backend');
        backendItem.connect('activate', () => this._startBackend());
        this.menu.addMenuItem(backendItem);
    }

    _runCurl(args, timeoutSeconds, callback) {
        const argv = ['curl', '-sS', '--max-time', String(timeoutSeconds)].concat(args);
        let proc;
        try {
            proc = Gio.Subprocess.new(
                argv,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
        } catch (e) {
            callback(false, '', String(e));
            return;
        }

        proc.communicate_utf8_async(null, null, (subprocess, result) => {
            try {
                const [, stdout, stderr] = subprocess.communicate_utf8_finish(result);
                callback(subprocess.get_successful(), stdout || '', stderr || '');
            } catch (e) {
                callback(false, '', String(e));
            }
        });
    }

    _getJson(path, callback) {
        this._runCurl([this._backendUrl + path], 4, (ok, stdout, stderr) => {
            if (!ok) {
                callback(false, null, stderr || 'sem resposta');
                return;
            }
            try {
                callback(true, JSON.parse(stdout), null);
            } catch (e) {
                callback(false, null, String(e));
            }
        });
    }

    _postJson(path, body, timeoutSeconds, callback) {
        this._runCurl([
            '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-d', JSON.stringify(body || {}),
            this._backendUrl + path
        ], timeoutSeconds, (ok, stdout, stderr) => {
            if (!ok) {
                callback(false, null, stderr || 'sem resposta');
                return;
            }
            try {
                callback(true, stdout ? JSON.parse(stdout) : {}, null);
            } catch (e) {
                callback(false, null, String(e));
            }
        });
    }

    _refreshStatus() {
        this._getJson('/api/applet/status', (ok, data, error) => {
            if (!ok || !data || !data.ok) {
                this.set_applet_icon_symbolic_name('network-offline-symbolic');
                this.set_applet_label('ZEUS');
                this.set_applet_tooltip('ZEUS offline: ' + _truncate(error || 'backend indisponivel', 80));
                this._statusItem.label.text = 'ZEUS offline';
                this._detailItem.label.text = _truncate(error || 'Backend local indisponivel', 96);
                return;
            }

            const provider = data.llm && data.llm.provider ? data.llm.provider : 'llm';
            const model = data.llm && data.llm.model ? data.llm.model : 'modelo';
            const configured = data.llm && data.llm.configured;
            this.set_applet_icon_symbolic_name(configured ? 'network-server-symbolic' : 'dialog-warning-symbolic');
            this.set_applet_label('ZEUS');
            this.set_applet_tooltip('ZEUS online: ' + provider + ' / ' + model);
            this._statusItem.label.text = configured ? 'ZEUS online' : 'ZEUS sem LLM';
            this._detailItem.label.text = _truncate(provider + ' · ' + model, 96);
        });
    }

    _sendChat() {
        if (this._busy) {
            return;
        }

        const text = this._entry.get_text().trim();
        if (!text) {
            return;
        }

        this._entry.set_text('');
        this._appendMessage('user', text);
        this._busy = true;
        this._statusItem.label.text = 'ZEUS pensando...';

        this._postJson('/api/applet/chat', {
            message: text,
            source: 'cinnamon_applet',
            client_id: 'zeus_cinnamon_applet'
        }, 90, (ok, data, error) => {
            this._busy = false;
            if (!ok || !data || data.error) {
                this._appendMessage('ai', 'Erro: ' + _truncate((data && data.error) || error || 'falha no chat', 160));
                this._refreshStatus();
                return;
            }
            this._appendMessage('ai', data.reply || 'Sem resposta.');
            this._refreshStatus();
        });
    }

    _startVoice() {
        this._postJson('/api/applet/voice/start', { duration: 10 }, 8, (ok, data, error) => {
            this._appendMessage('ai', ok ? 'Escuta ativada por 10s.' : 'Erro ao iniciar voz: ' + _truncate(error, 120));
        });
    }

    _startVision() {
        this._postJson('/api/applet/vision/analyze', {}, 8, (ok, data, error) => {
            this._appendMessage('ai', ok ? 'Analise de tela enviada para o ZEUS.' : 'Erro na visao: ' + _truncate(error, 120));
        });
    }

    _openHud() {
        Gio.AppInfo.launch_default_for_uri(this._backendUrl, null);
    }

    _startBackend() {
        const root = _projectRoot();
        const cmd = 'cd "' + root.replace(/"/g, '\\"') + '" && setsid .venv/bin/python -m apps.web_gui --headless > zeus_server.log 2>&1 < /dev/null &';
        GLib.spawn_command_line_async('bash -lc ' + JSON.stringify(cmd));
        this._appendMessage('ai', 'Solicitei inicio do backend.');
        Mainloop.timeout_add_seconds(3, () => {
            this._refreshStatus();
            return false;
        });
    }

    _appendMessage(role, text) {
        this._messages.push({ role: role, text: text });
        if (this._messages.length > MAX_MESSAGES) {
            this._messages.shift();
        }
        this._renderHistory();
    }

    _renderHistory() {
        if (!this._historySection) {
            return;
        }
        this._historySection.removeAll();

        if (this._messages.length === 0) {
            const empty = new PopupMenu.PopupMenuItem('Sem mensagens', { reactive: false });
            empty.label.add_style_class_name('zeus-applet-muted');
            this._historySection.addMenuItem(empty);
            return;
        }

        for (let i = 0; i < this._messages.length; i++) {
            const msg = this._messages[i];
            const prefix = msg.role === 'user' ? 'Voce: ' : 'ZEUS: ';
            const item = new PopupMenu.PopupMenuItem(prefix + _truncate(msg.text, 180), { reactive: false });
            item.label.add_style_class_name(msg.role === 'user' ? 'zeus-chat-message-user' : 'zeus-chat-message-ai');
            this._historySection.addMenuItem(item);
        }
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new ZeusApplet(orientation, panelHeight, instanceId);
}
