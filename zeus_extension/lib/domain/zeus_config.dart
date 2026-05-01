class ZeusConfig {
  ZeusConfig({
    required this.wsUrl,
    required this.httpUrl,
    this.token,
  });

  final String wsUrl;
  final String httpUrl;
  final String? token;

  static ZeusConfig defaults() => ZeusConfig(
        wsUrl: 'ws://127.0.0.1:8080/ws',
        httpUrl: 'http://127.0.0.1:8080/chat',
      );

  ZeusConfig copyWith({
    String? wsUrl,
    String? httpUrl,
    String? token,
  }) {
    return ZeusConfig(
      wsUrl: wsUrl ?? this.wsUrl,
      httpUrl: httpUrl ?? this.httpUrl,
      token: token ?? this.token,
    );
  }
}
