'use client';

import { useEffect, useRef, useCallback, useTransition } from 'react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Paperclip,
  SendIcon,
  XIcon,
  LoaderIcon,
  Sparkles,
  Command,
  GraduationCap,
  Book,
  Utensils,
  Calendar,
  Link as LinkIcon,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as React from 'react';
import { TextShimmer } from './text-shimmer';
import ReactMarkdown from 'react-markdown';


interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({
  minHeight,
  maxHeight,
}: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      if (reset) {
        textarea.style.height = `${minHeight}px`;
        return;
      }

      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(
        minHeight,
        Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY),
      );

      textarea.style.height = `${newHeight}px`;
    },
    [minHeight, maxHeight],
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = `${minHeight}px`;
    }
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

interface CommandSuggestion {
  icon: React.ReactNode;
  label: string;
  description: string;
  prefix: string;
}

interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  containerClassName?: string;
  showRing?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, showRing = true, ...props }, ref) => {
    const [isFocused, setIsFocused] = React.useState(false);

    return (
      <div className={cn('relative', containerClassName)}>
        <textarea
          className={cn(
            'border-input bg-background flex min-h-[80px] w-full rounded-md border px-3 py-2 text-sm',
            'transition-all duration-200 ease-in-out',
            'placeholder:text-muted-foreground',
            'disabled:cursor-not-allowed disabled:opacity-50',
            showRing
              ? 'focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none'
              : '',
            className,
          )}
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />

        {showRing && isFocused && (
          <motion.span
            className="ring-primary/30 pointer-events-none absolute inset-0 rounded-md ring-2 ring-offset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}

        {props.onChange && (
          <div
            className="bg-primary absolute right-2 bottom-2 h-2 w-2 rounded-full opacity-0"
            style={{
              animation: 'none',
            }}
            id="textarea-ripple"
          />
        )}
      </div>
    );
  },
);
Textarea.displayName = 'Textarea';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ url: string; title: string }>;
}

const SourceChips = ({ sources }: { sources: Array<{ url: string; title: string }> }) => {
  if (!sources || sources.length === 0) return null;
  
  return (
    <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-border/50">
      <p className="text-xs text-muted-foreground font-medium w-full">Sources:</p>
      {sources.map((source, i) => (
        <a 
          key={i} 
          href={source.url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-[10px] px-2 py-1 bg-slate-200 dark:bg-slate-800 hover:bg-amber-500 hover:text-white rounded-full transition-all flex items-center gap-1 group"
        >
          <LinkIcon size={10} className="group-hover:text-white" />
          {source.title || new URL(source.url).hostname}
        </a>
      ))}
    </div>
  );
};

const MessageBubble = ({ message }: { message: Message }) => {
  // Use a regex to extract the content inside <|thought|> tags
  const thoughtMatch = message.content.match(/<\|thought\|>([\s\S]*?)<\|answer\|>/);
  // Also handle closing tag only if starting tag is missing for partial streams
  const finalAnswerSplit = message.content.split('<|answer|>');
  let finalAnswer = finalAnswerSplit.length > 1 ? finalAnswerSplit[1] : message.content;
  
  // If parsing failed but we see tags, try to clean up
  if (!thoughtMatch && message.content.includes('<|answer|>')) {
     finalAnswer = message.content.substring(message.content.indexOf('<|answer|>') + 10);
  } else if (thoughtMatch) {
     // If we matched thoughts, the rest is the answer
     // This logic might need refinement depending on exact stream behavior
  }

  // Remove <|thought|>... part from final answer if it leaked in
  if (finalAnswer.includes('<|thought|>')) {
     finalAnswer = finalAnswer.replace(/<\|thought\|>[\s\S]*?<\|answer\|>/, '');
  }

  const thoughtContent = thoughtMatch ? thoughtMatch[1].trim() : null;

  return (
    <div className="space-y-2">
      {thoughtContent && (
        <details className="group cursor-pointer mb-2">
          <summary className="text-xs font-semibold text-amber-600 uppercase tracking-widest list-none flex items-center gap-1">
             <span className="inline-block transition-transform group-open:rotate-90">▶</span>
            🧠 View Reasoning Trace
          </summary>
          <div className="mt-2 text-sm italic text-slate-500 dark:text-slate-400 bg-white/50 dark:bg-black/20 p-3 rounded border border-amber-100 dark:border-amber-900/30">
            {thoughtContent}
          </div>
        </details>
      )}
      <div className="prose prose-slate prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown>{finalAnswer}</ReactMarkdown>
      </div>
      
      {message.sources && <SourceChips sources={message.sources} />}
    </div>
  );
};

export default function AnimatedAIChat() {
  const [value, setValue] = useState('');
  const [attachments, setAttachments] = useState<string[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [showInitialThinking, setShowInitialThinking] = useState(true);
  const [, startTransition] = useTransition();
  const [activeSuggestion, setActiveSuggestion] = useState<number>(-1);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight: 60,
    maxHeight: 200,
  });
  const [inputFocused, setInputFocused] = useState(false);
  const commandPaletteRef = useRef<HTMLDivElement>(null);

  const commandSuggestions: CommandSuggestion[] = [
    {
      icon: <GraduationCap className="h-4 w-4" />,
      label: 'Admissions',
      description: 'Ask about application process',
      prefix: '/admissions',
    },
    {
      icon: <Book className="h-4 w-4" />,
      label: 'Courses',
      description: 'Find course information',
      prefix: '/courses',
    },
    {
      icon: <Utensils className="h-4 w-4" />,
      label: 'Dining',
      description: 'Check dining options',
      prefix: '/dining',
    },
    {
      icon: <Calendar className="h-4 w-4" />,
      label: 'Events',
      description: 'Upcoming campus events',
      prefix: '/events',
    },
  ];

  useEffect(() => {
    if (value.startsWith('/') && !value.includes(' ')) {
      setShowCommandPalette(true);

      const matchingSuggestionIndex = commandSuggestions.findIndex((cmd) =>
        cmd.prefix.startsWith(value),
      );

      if (matchingSuggestionIndex >= 0) {
        setActiveSuggestion(matchingSuggestionIndex);
      } else {
        setActiveSuggestion(-1);
      }
    } else {
      setShowCommandPalette(false);
    }
  }, [value]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const commandButton = document.querySelector('[data-command-button]');

      if (
        commandPaletteRef.current &&
        !commandPaletteRef.current.contains(target) &&
        !commandButton?.contains(target)
      ) {
        setShowCommandPalette(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommandPalette) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveSuggestion((prev) =>
          prev < commandSuggestions.length - 1 ? prev + 1 : 0,
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveSuggestion((prev) =>
          prev > 0 ? prev - 1 : commandSuggestions.length - 1,
        );
      } else if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault();
        if (activeSuggestion >= 0) {
          const selectedCommand = commandSuggestions[activeSuggestion];
          setValue(selectedCommand.prefix + ' ');
          setShowCommandPalette(false);


        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setShowCommandPalette(false);
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) {
        handleSendMessage();
      }
    }
  };

  const handleSendMessage = async () => {
    if (!value.trim()) return;

    const userMessage = value.trim();
    setShowInitialThinking(false);
    setValue('');
    adjustHeight(true);
    setError(null);

    // Add user message to chat
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);

    startTransition(() => {
      setIsTyping(true);
    });

    // Create a new assistant message placeholder
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', sources: [] }
    ]);

    try {
      // Call FastAPI backend with streaming
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: userMessage,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to get response');
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessageContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (!dataStr) continue;
            
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'start') {
                // Keep the typing clean
              } else if (data.type === 'chunk') {
                assistantMessageContent += data.content;
                
                // Update the last message (the assistant's)
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage.role === 'assistant') {
                    lastMessage.content = assistantMessageContent;
                  }
                  return newMessages;
                });
                
                setIsTyping(false); // Stop "Thinking..." animation once we have first chunk
                
              } else if (data.type === 'complete') {
                // Update with final sources
                 setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage.role === 'assistant') {
                    lastMessage.content = assistantMessageContent; // Ensure full content
                    lastMessage.sources = data.sources;
                  }
                  return newMessages;
                });
              } else if (data.type === 'error') {
                 throw new Error(data.message);
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }

    } catch (err) {
      console.error('Chat error:', err);
      // Update the last assistant message to show error
      setMessages((prev) => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          // Only replace content if it was the generated one being streamed
          if (lastMessage.role === 'assistant') {
              lastMessage.content = `Sorry, I encountered an error: ${err instanceof Error ? err.message : 'Unknown error'}. Please make sure the backend is running.`;
          }
          return newMessages;
      });
    } finally {
      setIsTyping(false);
    }
  };

  const handleAttachFile = () => {
    const mockFileName = `file-${Math.floor(Math.random() * 1000)}.pdf`;
    setAttachments((prev) => [...prev, mockFileName]);
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const selectCommandSuggestion = (index: number) => {
    const selectedCommand = commandSuggestions[index];
    setValue(selectedCommand.prefix + ' ');
    setShowCommandPalette(false);


  };

  return (
    <div className="flex w-full overflow-x-hidden">
      <div className="text-foreground relative flex min-h-screen w-full flex-col items-center justify-end overflow-hidden bg-transparent pb-12">
        <div className="absolute inset-0 h-full w-full overflow-hidden">
          <div className="bg-primary/10 absolute top-0 left-1/4 h-96 w-96 animate-pulse rounded-full mix-blend-normal blur-[128px] filter" />
          <div className="bg-secondary/10 absolute right-1/4 bottom-0 h-96 w-96 animate-pulse rounded-full mix-blend-normal blur-[128px] filter delay-700" />
          <div className="bg-primary/10 absolute top-1/4 right-1/3 h-64 w-64 animate-pulse rounded-full mix-blend-normal blur-[96px] filter delay-1000" />
        </div>
        <div className="relative mx-auto w-full max-w-2xl">
          <motion.div
            className="relative z-10 space-y-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          >
            {/* Messages Display */}
            {messages.length > 0 && (
              <div className="mb-8 space-y-4 max-h-[400px] overflow-y-auto px-4 custom-scrollbar">
                {messages.map((message, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className={cn(
                      'rounded-lg p-4',
                      message.role === 'user'
                        ? 'bg-primary/10 ml-auto max-w-[80%]'
                        : 'bg-muted/50 mr-auto max-w-[90%]'
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {message.role === 'assistant' && (
                        <div className="bg-primary/20 flex h-8 w-8 items-center justify-center rounded-full flex-shrink-0">
                          <Sparkles className="text-primary h-4 w-4" />
                        </div>
                      )}
                      <div className="flex-1 w-full overflow-hidden">
                         {message.role === 'user' ? (
                            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                         ) : (
                            <MessageBubble message={message} />
                         )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}

            <div className="space-y-3 text-center min-h-[120px]">
              <AnimatePresence mode="popLayout">
                {showInitialThinking && (
                  <motion.div
                    key="intro-content"
                    exit={{ opacity: 0, scale: 0.95, filter: "blur(10px)" }}
                    transition={{ duration: 0.5 }}
                    className="flex flex-col items-center justify-center space-y-3"
                  >
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2, duration: 0.5 }}
                      className="inline-block"
                    >
                      <h1 className="pb-1 text-3xl font-medium tracking-tight">
                        How can Campus GPT help today?
                      </h1>
                      <motion.div
                        className="via-primary/50 h-px bg-gradient-to-r from-transparent to-transparent"
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: '100%', opacity: 1 }}
                        transition={{ delay: 0.5, duration: 0.8 }}
                      />
                    </motion.div>
                    <motion.p
                      className="text-muted-foreground text-sm"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 }}
                    >
                      Type a command or ask a question
                    </motion.p>
                  </motion.div>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {isTyping && (
                  <motion.div
                    className="flex items-center justify-center gap-3"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <div className="bg-primary/10 flex h-7 w-8 items-center justify-center rounded-full text-center">
                      <Sparkles className="text-primary h-4 w-4" />
                    </div>
                    <div className="text-muted-foreground flex items-center gap-2 text-sm">
                      <TextShimmer className='font-mono text-sm' duration={1}>
                        Thinking...
                      </TextShimmer>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <motion.div
              className="border-border bg-card/80 relative rounded-2xl border shadow-2xl backdrop-blur-2xl"
              initial={{ scale: 0.98 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.1 }}
            >
              <AnimatePresence>
                {showCommandPalette && (
                  <motion.div
                    ref={commandPaletteRef}
                    className="border-border bg-background/90 absolute right-4 bottom-full left-4 z-50 mb-2 overflow-hidden rounded-lg border shadow-lg backdrop-blur-xl"
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 5 }}
                    transition={{ duration: 0.15 }}
                  >
                    <div className="bg-background py-1">
                      {commandSuggestions.map((suggestion, index) => (
                        <motion.div
                          key={suggestion.prefix}
                          className={cn(
                            'flex cursor-pointer items-center gap-2 px-3 py-2 text-xs transition-colors',
                            activeSuggestion === index
                              ? 'bg-primary/20 text-foreground'
                              : 'text-muted-foreground hover:bg-primary/10',
                          )}
                          onClick={() => selectCommandSuggestion(index)}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: index * 0.03 }}
                        >
                          <div className="text-primary flex h-5 w-5 items-center justify-center">
                            {suggestion.icon}
                          </div>
                          <div className="font-medium">{suggestion.label}</div>
                          <div className="text-muted-foreground ml-1 text-xs">
                            {suggestion.prefix}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="p-4">
                <Textarea
                  ref={textareaRef}
                  value={value}
                  onChange={(e) => {
                    setValue(e.target.value);
                    adjustHeight();
                  }}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setInputFocused(true)}
                  onBlur={() => setInputFocused(false)}
                  placeholder="Ask about NKU campus life..."
                  containerClassName="w-full"
                  className={cn(
                    'w-full px-4 py-3',
                    'resize-none',
                    'bg-transparent',
                    'border-none',
                    'text-foreground text-sm',
                    'focus:outline-none',
                    'placeholder:text-muted-foreground',
                    'min-h-[60px]',
                  )}
                  style={{
                    overflow: 'hidden',
                  }}
                  showRing={false}
                />
              </div>

              <AnimatePresence>
                {attachments.length > 0 && (
                  <motion.div
                    className="flex flex-wrap gap-2 px-4 pb-3"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    {attachments.map((file, index) => (
                      <motion.div
                        key={index}
                        className="bg-primary/5 text-muted-foreground flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                      >
                        <span>{file}</span>
                        <button
                          onClick={() => removeAttachment(index)}
                          className="text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <XIcon className="h-3 w-3" />
                        </button>
                      </motion.div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="border-border flex items-center justify-between gap-4 border-t p-4">
                <div className="flex items-center gap-3">
                  <motion.button
                    type="button"
                    onClick={handleAttachFile}
                    whileTap={{ scale: 0.94 }}
                    className="group text-muted-foreground hover:text-foreground relative rounded-lg p-2 transition-colors"
                  >
                    <Paperclip className="h-4 w-4" />
                    <motion.span
                      className="bg-primary/10 absolute inset-0 rounded-lg opacity-0 transition-opacity group-hover:opacity-100"
                      layoutId="button-highlight"
                    />
                  </motion.button>
                  <motion.button
                    type="button"
                    data-command-button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowCommandPalette((prev) => !prev);
                    }}
                    whileTap={{ scale: 0.94 }}
                    className={cn(
                      'group text-muted-foreground hover:text-foreground relative rounded-lg p-2 transition-colors',
                      showCommandPalette && 'bg-primary/20 text-foreground',
                    )}
                  >
                    <Command className="h-4 w-4" />
                    <motion.span
                      className="bg-primary/10 absolute inset-0 rounded-lg opacity-0 transition-opacity group-hover:opacity-100"
                      layoutId="button-highlight"
                    />
                  </motion.button>
                </div>

                <motion.button
                  type="button"
                  onClick={handleSendMessage}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.98 }}
                  disabled={isTyping || !value.trim()}
                  className={cn(
                    'rounded-lg px-4 py-2 text-sm font-medium transition-all',
                    'flex items-center gap-2',
                    value.trim()
                      ? 'bg-primary text-primary-foreground shadow-primary/10 shadow-lg'
                      : 'bg-muted/50 text-muted-foreground',
                  )}
                >
                  {isTyping ? (
                    <LoaderIcon className="h-4 w-4 animate-[spin_2s_linear_infinite]" />
                  ) : (
                    <SendIcon className="h-4 w-4" />
                  )}
                  <span>Send</span>
                </motion.button>
              </div>
            </motion.div>

            <div className="flex flex-wrap items-center justify-center gap-2">
              {commandSuggestions.map((suggestion, index) => (
                <motion.button
                  key={suggestion.prefix}
                  onClick={() => selectCommandSuggestion(index)}
                  className="group bg-primary/5 text-muted-foreground hover:bg-primary/10 hover:text-foreground relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  {suggestion.icon}
                  <span>{suggestion.label}</span>
                  <motion.div
                    className="border-border/50 absolute inset-0 rounded-lg border"
                    initial={false}
                    animate={{
                      opacity: [0, 1],
                      scale: [0.98, 1],
                    }}
                    transition={{
                      duration: 0.3,
                      ease: 'easeOut',
                    }}
                  />
                </motion.button>
              ))}
            </div>
          </motion.div>
        </div>



        {inputFocused && (
          <motion.div
            className="from-primary via-primary/80 to-secondary pointer-events-none fixed z-0 h-[50rem] w-[50rem] rounded-full bg-gradient-to-r opacity-[0.02] blur-[96px]"
            animate={{
              x: mousePosition.x - 400,
              y: mousePosition.y - 400,
            }}
            transition={{
              type: 'spring',
              damping: 25,
            }}
          />
        )}
      </div>
    </div>
  );
}



const rippleKeyframes = `
@keyframes ripple {
  0% { transform: scale(0.5); opacity: 0.6; }
  100% { transform: scale(2); opacity: 0; }
}
`;

if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.innerHTML = rippleKeyframes;
  document.head.appendChild(style);
}
