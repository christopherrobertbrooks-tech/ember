import React, { useEffect, useRef } from 'react';

export default function ChatBox({ messages, isBotTyping }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isBotTyping]);

  return (
    <div className="chat-box">
      {messages.length === 0 && (
        <div className="message-wrapper system">
          <div className="message system">
            Start a conversation with Ember...
          </div>
        </div>
      )}
      {messages.map((msg) => (
        <div key={msg.id} className={`message-wrapper ${msg.role}`}>
          <div className={`message ${msg.role}`}>
            {msg.image && (
              <div style={{ marginBottom: msg.content ? '8px' : '0' }}>
                <img src={msg.image} alt="Message Attachment" style={{ maxWidth: '100%', borderRadius: '8px' }} />
              </div>
            )}
            {msg.content}
          </div>
        </div>
      ))}
      {isBotTyping && (
        <div className="message-wrapper bot">
          <div className="message bot">
            <em>Ember is typing...</em>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
