import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/zeus_provider.dart';
import '../../domain/models.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  void _sendMessage() {
    if (_controller.text.trim().isEmpty) return;
    ref.read(zeusProvider.notifier).sendMessage(_controller.text);
    _controller.clear();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(zeusProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("ZEUS_NEURAL_LINK"),
            if (state.lastStatus.isNotEmpty)
              Text(
                state.lastStatus.toUpperCase(),
                style: const TextStyle(fontSize: 9, color: Colors.white38, letterSpacing: 1),
                overflow: TextOverflow.ellipsis,
              ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.circle, color: state.isConnected ? Colors.green : Colors.red, size: 12),
            onPressed: () {},
          ),
        ],
      ),
      body: Stack(
        children: [
          Column(
            children: [
              Expanded(
                child: ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(15),
                  itemCount: state.chatHistory.length + ((state.isThinking || state.streamingText.isNotEmpty) ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == state.chatHistory.length) {
                      return _buildThinkingIndicator(state.streamingText);
                    }
                    final msg = state.chatHistory[index];
                    return _buildChatBubble(msg);
                  },
                ),
              ),
              if (state.partialSpeech.isNotEmpty) _buildPartialSpeechOverlay(state.partialSpeech),
              _buildInputArea(state),
            ],
          ),
          _buildMatrixOverlay(),
        ],
      ),
    );
  }

  Widget _buildThinkingIndicator(String streamingText) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 10),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFF00FF41).withOpacity(0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00FF41)),
                ),
                const SizedBox(width: 15),
                Text(
                  streamingText.isEmpty ? "ANALYZING_INPUT..." : "RECEIVING_DATA...",
                  style: TextStyle(color: const Color(0xFF00FF41).withOpacity(0.7), fontSize: 10, letterSpacing: 2),
                ),
              ],
            ),
            if (streamingText.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                streamingText,
                style: const TextStyle(color: Colors.white, fontSize: 14, letterSpacing: 0.5),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildPartialSpeechOverlay(String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      margin: const EdgeInsets.symmetric(horizontal: 15, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFF00FF41).withOpacity(0.1),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: const Color(0xFF00FF41).withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.mic, color: Color(0xFF00FF41), size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Color(0xFF00FF41), fontSize: 14, fontStyle: FontStyle.italic),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatBubble(ZeusMessage msg) {
    bool isUser = msg.type == MessageType.user;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFF00FF41).withOpacity(0.05) : Colors.black,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(10),
            topRight: const Radius.circular(10),
            bottomLeft: isUser ? const Radius.circular(10) : Radius.zero,
            bottomRight: isUser ? Radius.zero : const Radius.circular(10),
          ),
          border: Border.all(
            color: isUser ? const Color(0xFF00FF41).withOpacity(0.3) : const Color(0xFF00F0FF).withOpacity(0.2),
          ),
        ),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(isUser ? Icons.person_outline : Icons.terminal, 
                     size: 10, 
                     color: isUser ? const Color(0xFF00FF41) : const Color(0xFF00F0FF)),
                const SizedBox(width: 5),
                Text(
                  isUser ? "USER_ID" : "ZEUS_CORE",
                  style: TextStyle(
                    color: isUser ? const Color(0xFF00FF41) : const Color(0xFF00F0FF),
                    fontSize: 9,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(msg.text, style: const TextStyle(fontSize: 14, letterSpacing: 0.5)),
          ],
        ),
      ),
    );
  }

  Widget _buildInputArea(ZeusState state) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: const BoxDecoration(
        color: Color(0xFF0D0D0D),
        border: Border(top: BorderSide(color: Color(0xFF00FF41), width: 0.2)),
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                style: const TextStyle(color: Color(0xFF00FF41), fontSize: 14),
                decoration: const InputDecoration(
                  hintText: ">_ system_input",
                  hintStyle: TextStyle(color: Colors.white12),
                  border: InputBorder.none,
                ),
                onSubmitted: (_) => _sendMessage(),
              ),
            ),
            IconButton(
              icon: Icon(
                state.isListening ? Icons.graphic_eq : Icons.mic, 
                color: state.isListening ? Colors.red : const Color(0xFF00FF41)
              ),
              onPressed: () {
                ref.read(zeusProvider.notifier).toggleListening();
              },
            ),
            IconButton(
              icon: const Icon(Icons.send_rounded, color: Color(0xFF00F0FF), size: 20),
              onPressed: _sendMessage,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMatrixOverlay() {
    return IgnorePointer(
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              const Color(0xFF00FF41).withOpacity(0.03),
              Colors.transparent,
              const Color(0xFF00FF41).withOpacity(0.03),
            ],
          ),
        ),
      ),
    );
  }
}
