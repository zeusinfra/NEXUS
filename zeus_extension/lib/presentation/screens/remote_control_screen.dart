import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/zeus_provider.dart';

class RemoteControlScreen extends ConsumerStatefulWidget {
  const RemoteControlScreen({super.key});

  @override
  ConsumerState<RemoteControlScreen> createState() => _RemoteControlScreenState();
}

class _RemoteControlScreenState extends ConsumerState<RemoteControlScreen> {
  final TextEditingController _cmdController = TextEditingController();
  final List<String> _quickCommands = [
    "top -n 1",
    "df -h",
    "ps aux | grep python",
    "uptime",
    "systemctl status zeus_core"
  ];

  void _executeCommand(String command) {
    if (command.trim().isEmpty) return;
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("CONFIRMAR AÇÃO CRÍTICA"),
        content: Text("Deseja executar o comando:\n\n$command"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("CANCELAR", style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            onPressed: () {
              ref.read(zeusProvider.notifier).executeSystemAction(command);
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Comando enviado para o Guardian...")),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text("EXECUTAR"),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _cmdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("SECURE REMOTE CONTROL")),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("QUICK ACTIONS", style: TextStyle(color: Colors.cyan, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              children: _quickCommands.map((cmd) => ActionChip(
                label: Text(cmd, style: const TextStyle(fontSize: 12)),
                backgroundColor: Colors.white10,
                onPressed: () => _executeCommand(cmd),
              )).toList(),
            ),
            const SizedBox(height: 30),
            const Text("CUSTOM COMMAND", style: TextStyle(color: Colors.cyan, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            TextField(
              controller: _cmdController,
              decoration: InputDecoration(
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.05),
                hintText: "Digite um comando linux...",
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.play_arrow, color: Colors.cyan),
                  onPressed: () => _executeCommand(_cmdController.text),
                ),
              ),
            ),
            const SizedBox(height: 30),
            const Text("SYSTEM GUARDIAN LOG", style: TextStyle(color: Colors.white54, fontSize: 12)),
            const SizedBox(height: 10),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.white10),
                ),
                child: const SingleChildScrollView(
                  child: Text(
                    "> ZEUS Guardian: Monitorando sessões remotas...\n> Aguardando comandos...",
                    style: TextStyle(fontFamily: 'monospace', color: Colors.greenAccent, fontSize: 12),
                  ),
                ),
              ),
            )
          ],
        ),
      ),
    );
  }
}
