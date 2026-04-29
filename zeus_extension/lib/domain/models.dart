enum MessageType { user, ai, system, alert }

class ZeusMessage {
  final String text;
  final MessageType type;
  final DateTime timestamp;

  ZeusMessage({
    required this.text,
    required this.type,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  factory ZeusMessage.fromJson(Map<String, dynamic> json) {
    String typeStr = json['type'] ?? 'CHAT_AI';
    MessageType type;
    if (typeStr.contains('USER')) {
      type = MessageType.user;
    } else if (typeStr.contains('AI')) {
      type = MessageType.ai;
    } else if (typeStr.contains('alert')) {
      type = MessageType.alert;
    } else {
      type = MessageType.system;
    }

    return ZeusMessage(
      text: json['message'] ?? json['text'] ?? '',
      type: type,
    );
  }
}

class SystemStatus {
  final double cpu;
  final double ram;
  final String mood;
  final int activeTasks;

  SystemStatus({
    required this.cpu,
    required this.ram,
    required this.mood,
    required this.activeTasks,
  });

  factory SystemStatus.fromJson(Map<String, dynamic> json) {
    return SystemStatus(
      cpu: (json['cpu'] ?? 0.0).toDouble(),
      ram: (json['ram'] ?? 0.0).toDouble(),
      mood: json['mood'] ?? 'UNKNOWN',
      activeTasks: json['active_tasks'] ?? 0,
    );
  }
}
