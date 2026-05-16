from nexus_core.conversation.sqlite_conversation_memory import SQLiteConversationMemory


def test_conversation_memory_recalls_recent_and_similar(tmp_path):
    memory = SQLiteConversationMemory(str(tmp_path / "conversation.db"))
    memory.add_turn("s1", "iced", "user", "Vamos melhorar os baloes de conversa Iced")
    memory.add_turn("s1", "iced", "assistant", "Plano para melhorar bubbles e markdown")
    memory.add_turn(
        "s2",
        "iced",
        "user",
        "A memoria das conversas precisa lembrar assuntos parecidos",
    )

    block = memory.build_context_block(
        "melhorar memoria conversa parecida", session_id="s1", client_id="iced"
    )

    assert "HISTORICO RECENTE" in block
    assert "MEMORIAS DE CONVERSAS PARECIDAS" in block
    assert "baloes de conversa" in block
    assert "lembrar assuntos parecidos" in block
