import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const BACKEND_API_URL = process.env.NEXT_PUBLIC_API_URL;

// MathJax configuration
const mathJaxConfig = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    packages: {'[+]': ['ams', 'newcommand', 'configmacros']},
    processEscapes: true,
    processEnvironments: true
  },
  svg: {
    fontCache: 'global'
  },
  options: {
    renderActions: {
      addMenu: [0, '', '']
    }
  }
};

function App() {
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState(null);
  const [waiting, setWaiting] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mathJaxLoaded, setMathJaxLoaded] = useState(false);

  const [userScrolled, setUserScrolled] = useState(false);
  const [lastMsgCount, setLastMsgCount] = useState(0);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null); 
  const mathJaxTimeoutRef = useRef(null);
  const prevMessagesRef = useRef([]);

  // Load MathJax
  useEffect(() => {
    if (!window.MathJax && !mathJaxLoaded) {
      // Configure MathJax before loading
      window.MathJax = mathJaxConfig;
      
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.min.js';
      script.async = true;
      script.onload = () => {
        console.log('MathJax loaded successfully');
        setMathJaxLoaded(true);
      };
      script.onerror = () => {
        console.error('Failed to load MathJax');
      };
      document.head.appendChild(script);
    } else if (window.MathJax) {
      setMathJaxLoaded(true);
    }
  }, [mathJaxLoaded]);

  // Retypeset MathJax when messages change
  useEffect(() => {
    if (mathJaxLoaded && window.MathJax && window.MathJax.typesetPromise) {
      // Only retypeset if messages actually changed
      if (JSON.stringify(messages) !== JSON.stringify(prevMessagesRef.current)) {
        prevMessagesRef.current = messages;
        
        // Clear existing timeout
        if (mathJaxTimeoutRef.current) {
          clearTimeout(mathJaxTimeoutRef.current);
        }
        
        // Debounce: Wait 300ms before typesets
        mathJaxTimeoutRef.current = setTimeout(() => {
          window.MathJax.typesetPromise().catch((err) => {
            console.warn('MathJax typeset error:', err);
          });
        }, 300);
      }
    }
  }, [messages, mathJaxLoaded]);

  // smart scrolling
  const handleScroll = () => {
    if (!messagesContainerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    
    setUserScrolled(!isAtBottom);
  };

  useEffect(() => {
    if (messages.length > lastMsgCount && !userScrolled) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    setLastMsgCount(messages.length);
  }, [messages.length, userScrolled]);

  // Poll for updates when we have an active session
  useEffect(() => {
    if (!sessionId || status === "completed") return;

    const pollChat = async () => {
      try {
        const res = await fetch(`${BACKEND_API_URL}/chat/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setMessages(data.messages || []);
          setStatus(data.status);
          setWaiting(data.waiting);
        }
      } catch (err) {
        console.error("Error polling chat:", err);
      }
    };

    // Poll every 2 seconds while processing or waiting for approval
    const interval = setInterval(pollChat, 2000);
    
    // Initial poll
    pollChat();

    return () => clearInterval(interval);
  }, [sessionId, status]);

  // Enhanced math formatting function
  const formatMathContent = (content) => {
    if (!content) return content;
    
    let formatted = content;
    
    // Escape any existing # characters that aren't part of LaTeX
    formatted = formatted.replace(/#/g, '\\#');
    
    // Only apply math formatting to content that looks like mathematical expressions
    const hasMathIndicators = /[=+\-*/^_√∫∂∞πθαβγδωλμσ]|sin|cos|tan|log|ln|sqrt|integral|derivative|solve|equation/i.test(content);
    
    if (hasMathIndicators) {
      // Simple and safe mathematical expressions
      const mathPatterns = [
        // Simple fractions with numbers only
        { pattern: /\b(\d+)\/(\d+)\b/g, replacement: '\\frac{$1}{$2}' },
        // Mathematical symbols
        { pattern: /π/g, replacement: '\\pi' },
        { pattern: /∞/g, replacement: '\\infty' },
        { pattern: /∫/g, replacement: '\\int' },
        { pattern: /∂/g, replacement: '\\partial' },
        // Greek letters as whole words
        { pattern: /\bpi\b/g, replacement: '\\pi' },
        { pattern: /\btheta\b/g, replacement: '\\theta' },
        { pattern: /\balpha\b/g, replacement: '\\alpha' },
        { pattern: /\bbeta\b/g, replacement: '\\beta' },
        // Square root with simple content
        { pattern: /sqrt\(([^)]+)\)/g, replacement: '\\sqrt{$1}' },
        { pattern: /√\(([^)]+)\)/g, replacement: '\\sqrt{$1}' },
      ];

      // Apply patterns safely
      mathPatterns.forEach(({ pattern, replacement }) => {
        try {
          formatted = formatted.replace(pattern, replacement);
        } catch (e) {
          console.warn('Pattern replacement error:', e);
        }
      });

      // Only wrap simple equations in display math (avoid complex content)
      const simpleEquationPattern = /^[\s]*([a-zA-Z0-9\s+\-*/=().^_]+)[\s]*$/;
      if (simpleEquationPattern.test(formatted) && formatted.includes('=')) {
        if (!formatted.includes('$')) {
          formatted = `$$${formatted.trim()}$$`;
        }
      }
    }

    return formatted;
  };

  const sendMessage = async () => {
    if (!message.trim()) return;

    try {
      setLoading(true);
      setUserScrolled(false);

      const res = await fetch(`${BACKEND_API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ 
          topic: message,
          session_id: sessionId  // Continue existing session if available
        }),
      });
      
      if (res.ok) {
        const data = await res.json();
        
        if (!sessionId) {
          // New session
          setSessionId(data.session_id);
        }
        
        setMessages(data.messages || []);
        setStatus(data.status);
        setWaiting(data.waiting);
        setMessage("");  // Clear input
      } else {
        const errorData = await res.json();
        console.error("Error:", errorData);
      }
    } catch (err) {
      console.error("Error sending message:", err);
    } finally {
      setLoading(false);
    }
  };

  const sendFeedback = async () => {
    if (!message.trim() || !sessionId) return;

    try {
      setLoading(true);
      setUserScrolled(false);
      const res = await fetch(`${BACKEND_API_URL}/human-input`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials:"include",
        body: JSON.stringify({
          session_id: sessionId,
          feedback: message,
        }),
      });
      
      if (res.ok) {
        setMessage("");  // Clear input
        setWaiting(null);
        setStatus("processing");
      } else {
        const errorData = await res.json();
        console.error("Error:", errorData);
      }
    } catch (err) {
      console.error("Error sending feedback:", err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusDisplay = () => {
    switch (status) {
      case "processing": return "🔄 Processing...";
      case "waiting_for_approval": return "⏳ Waiting for your approval";
      case "completed": return "✅ Completed";
      case "error": return "❌ Error";
      default: return "";
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case "processing": return "#007bff";
      case "waiting_for_approval": return "#ffc107";
      case "completed": return "#28a745";
      case "error": return "#dc3545";
      default: return "#6c757d";
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setStatus(null);
    setWaiting(null);
    setMessage("");
    setLoading(false);
    setUserScrolled(false);
    setLastMsgCount(0);
  };

  return (
    <div className="app-container">
      <div className="chat-window">
        <div className="chat-header">
          <div className="header-content">
            <h2>Math Assistant</h2>
            {status && (
              <div 
                className="status-badge" 
                style={{ backgroundColor: getStatusColor() }}
              >
                {getStatusDisplay()}
              </div>
            )}
          </div>
          {sessionId && (
            <div className="session-controls">
              <button onClick={startNewChat} className="new-chat-btn">
                + New Chat
              </button>
            </div>
          )}
        </div>

        <div className="chat-messages" ref={messagesContainerRef} onScroll={handleScroll}>
          {messages.length === 0 && !sessionId && (
            <div className="welcome-message">
              <div className="welcome-content">
                <h3>Welcome to Math Agent!</h3>
                <p>I will help understand mathematical problems in a step by step manner.</p>
                <div className="example-questions">
                  <p><strong>Try asking your doubts:</strong></p>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message ${msg.role === "user" ? "user" : "assistant"}`}
            >
              <div className="message-content">
                <div className="message-text">
                  <div 
                    dangerouslySetInnerHTML={{
                      __html: formatMathContent(msg.content || '').replace(/\n/g, '<br/>')
                    }}
                  />
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="message assistant">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <div className="message-text">
                  {status === "processing" ? "Working on your problem..." : "Processing..."}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input">
          <div className="input-container">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={
                waiting 
                  ? "Type 'approve' to accept the solution, or provide feedback..." 
                  : "Ask me a math question..."
              }
              disabled={loading}
              rows={1}
              className="message-input"
            />
            <button
              onClick={waiting ? sendFeedback : sendMessage}
              disabled={loading || !message.trim()}
              className={`send-button ${waiting ? 'feedback-mode' : ''}`}
            >
              {loading ? (
                <div className="button-spinner"></div>
              ) : waiting ? (
                "💬"
              ) : (
                "➤"
              )}
            </button>
          </div>
          
          {waiting && (
            <div className="feedback-hint">
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;