(function(){
  const messagesEl = document.getElementById('messages');
  const form = document.getElementById('composer');
  const input = document.getElementById('input');

  function addMessage(text, who){
    const el = document.createElement('div');
    el.className = 'message ' + (who==='me'?'user':'ai');
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = wsProto + '//' + location.host + '/ws';
  let ws;
  function connect(){
    ws = new WebSocket(wsUrl);
    ws.addEventListener('open', ()=>{
      addMessage('Conectado ao Nexus.', 'ai');
    });
    ws.addEventListener('message', (ev)=>{
      try{
        const data = JSON.parse(ev.data);
        const type = data.type || data['event'] || '';
        if(type === 'CHAT_AI'){
          addMessage(data.message || (data.payload && data.payload.text) || JSON.stringify(data), 'ai');
        } else if(type === 'CHAT_USER'){
          addMessage(data.message || data.payload?.text || 'Você', 'me');
        } else if(type === 'HUD_STATUS'){
          // ignore or show small
        } else {
          // fallback: show raw
          // console.log('recv', data)
        }
      }catch(e){
        // ignore non-json
      }
    });
    ws.addEventListener('close', ()=>{
      addMessage('Desconectado, tentando reconectar...', 'ai');
      setTimeout(connect, 2000);
    });
  }
  connect();

  form.addEventListener('submit', (e)=>{
    e.preventDefault();
    const v = input.value.trim();
    if(!v) return;
    const payload = {type:'user_input', payload:{text: v}};
    try{
      ws.send(JSON.stringify(payload));
      addMessage(v, 'me');
      input.value = '';
    }catch(e){
      addMessage('Falha ao enviar — desconectado.', 'ai');
    }
  });
})();