import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ScrollArea } from "../components/ui/scroll-area";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
// import { Input } from "../components/ui/input";
import { Card } from "../components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Mic, MicOff, Send, Volume2, VolumeX, Sparkles } from "lucide-react";
import ChatMessage from "../components/ChatMessage";
import { seedMessages, quickPrompts } from "../mock/mock";
import { useToast } from "../hooks/use-toast";

const SESSION_KEY = "chat.session.id";
const MESSAGES_KEY = "chat.messages";
const TTS_KEY = "chat.tts";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = BACKEND_URL ? `${BACKEND_URL}/api` : undefined; // must be provided by env

function getSessionId() {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
  localStorage.setItem(SESSION_KEY, sid);
  return sid;
}

export default function Chat() {
  const { toast } = useToast();
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem(MESSAGES_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch {}
    }
    return seedMessages;
  });

  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [tts, setTts] = useState(() => localStorage.getItem(TTS_KEY) === "1");
  const [usingServer, setUsingServer] = useState(false);

  const scrollRef = useRef(null);
  const recognitionRef = useRef(null);
  const interimRef = useRef("");
  const speakingRef = useRef(false);
  const esRef = useRef(null);

  // Persist messages
  useEffect(() => {
    localStorage.setItem(MESSAGES_KEY, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    localStorage.setItem(TTS_KEY, tts ? "1" : "0");
  }, [tts]);

  useEffect(() => { getSessionId(); }, []);

  // Auto-scroll to bottom smoothly
  useEffect(() => {
    if (!scrollRef.current) return;
    try {
      const el = scrollRef.current;
      el.scrollTo({ top: el.scrollHeight + 200, behavior: "smooth" });
    } catch {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight + 200;
    }
  }, [messages]);

  const deafen = useCallback(() => {
    if (esRef.current) {
      try { esRef.current.close(); } catch {}
      esRef.current = null;
    }
  }, []);

  useEffect(() => () => { deafen(); }, [deafen]);

  const onSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg = { id: `m-${Date.now()}`, role: "user", content: text, ts: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");

    // create assistant placeholder and stream into it
    const asstId = `a-${Date.now()}`;
    const asstMsg = { id: asstId, role: "assistant", content: "", ts: Date.now() };
    setMessages((m) => [...m, asstMsg]);

    // Prefer real backend SSE if API is configured
    if (!API) {
      toast({ title: "Backend absent", description: "La clé REACT_APP_BACKEND_URL n'est pas configurée. Mock local utilisé." });
      // Fallback: local mock (kept for dev safety)
      const { simulateAIResponse } = await import("../mock/mock");
      try {
        await simulateAIResponse(text, (acc) => {
          setMessages((m) => m.map((mm) => (mm.id === asstId ? { ...mm, content: acc } : mm)));
        });
      } catch (e) {
        toast({ title: "Erreur", description: "La réponse (mock) a échoué." });
      }
      return;
    }

    try {
      // Close any previous stream
      deafen();

      const sid = getSessionId();
      const url = `${API}/chat/stream?q=${encodeURIComponent(text)}&sessionId=${encodeURIComponent(sid)}&provider=kernel&model=local`;
      const es = new EventSource(url);
      esRef.current = es;
      setUsingServer(true);

      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "session") {
            // nothing to do: session_id already known client-side
          } else if (data.type === "content") {
            const acc = data.content || "";
            setMessages((m) => m.map((mm) => (mm.id === asstId ? { ...mm, content: (mm.content || "") + acc } : mm)));
          } else if (data.type === "complete") {
            es.close();
            esRef.current = null;
            // Speak
            if (tts && "speechSynthesis" in window && !speakingRef.current) {
              const msg = (prev => prev.find((x) => x.id === asstId)?.content)(messages);
              const finalText = msg || document.querySelector(`[data-mid="${asstId}"]`)?.textContent || "";
              if (finalText) {
                speakingRef.current = true;
                const utter = new SpeechSynthesisUtterance(finalText);
                utter.lang = "fr-FR";
                utter.rate = 1;
                utter.onend = () => { speakingRef.current = false; };
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utter);
              }
            }
          } else if (data.type === "error") {
            es.close();
            esRef.current = null;
            toast({ title: "Erreur serveur", description: data.error || "Flux interrompu." });
          }
        } catch (err) {
          console.error("Parse SSE error", err);
        }
      };

      es.onerror = (e) => {
        console.error("SSE error", e);
        try { es.close(); } catch {}
        esRef.current = null;
        toast({ title: "Connexion perdue", description: "Requête SSE interrompue, bascule en mock." });
      };
    } catch (e) {
      console.error(e);
      toast({ title: "Erreur", description: "La requête SSE a échoué." });
    }
  }, [API, deafen, input, tts, toast, messages]);

  const startListening = useCallback(() => {
    try {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        toast({ title: "Micro non supporté", description: "La reconnaissance vocale n'est pas disponible sur ce navigateur." });
        return;
      }
      const rec = new SR();
      rec.lang = "fr-FR";
      rec.interimResults = true;
      rec.continuous = false;

      rec.onresult = (e) => {
        let interim = "";
        let final = "";
        for (let i = 0; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) final += res[0].transcript;
          else interim += res[0].transcript;
        }
        interimRef.current = interim;
        setInput((prev) => (final ? (prev ? prev + " " : "") + final : prev));
      };

      rec.onerror = (ev) => {
        console.error(ev);
        toast({ title: "Erreur micro", description: "Impossible d'utiliser le micro maintenant." });
        setListening(false);
      };
      rec.onend = () => {
        setListening(false);
      };

      recognitionRef.current = rec;
      setListening(true);
      rec.start();
    } catch (e) {
      console.error(e);
      toast({ title: "Erreur", description: "La reconnaissance vocale a échoué." });
      setListening(false);
    }
  }, [toast]);

  const stopListening = useCallback(() => {
    const rec = recognitionRef.current;
    if (rec) {
      try { rec.stop(); } catch {}
    }
    setListening(false);
  }, []);

  const Header = useMemo(
    () => (
      <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
        <div className="max-w-screen-sm mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h1 className="text-base font-semibold">Mon IA</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <VolumeX className={tts ? "hidden" : "h-4 w-4 text-muted-foreground"} />
              <Volume2 className={tts ? "h-4 w-4 text-primary" : "hidden"} />
              <Switch checked={tts} onCheckedChange={setTts} aria-label="Activer la voix" />
            </div>
          </div>
        </div>
      </div>
    ),
    [tts]
  );

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {Header}

      <main className="flex-1">
        <div className="max-w-screen-sm mx-auto px-3 pb-28 pt-3">
          <Card className="p-3 mb-3">
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((q, idx) => (
                <Badge
                  key={idx}
                  variant="secondary"
                  className="cursor-pointer hover:opacity-90"
                  onClick={() => setInput(q)}
                >
                  {q}
                </Badge>
              ))}
            </div>
          </Card>

          <ScrollArea className="h-[58vh] rounded-md border" >
            <div className="p-3 space-y-4">
              {messages.map((m) => (
                <div key={m.id} data-mid={m.id}>
                  <ChatMessage message={m} />
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 bg-background/90 backdrop-blur border-t">
        <div className="max-w-screen-sm mx-auto px-3 py-2">
          <div className="flex items-end gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant={listening ? "destructive" : "secondary"}
                    className="shrink-0"
                    onClick={listening ? stopListening : startListening}
                  >
                    {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {listening ? "Arrêter" : "Parler"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Écris ou dicte ton message..."
              className="min-h-[44px] max-h-[132px] resize-y"
            />

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button onClick={onSend} disabled={!input.trim()} className="shrink-0">
                    Envoyer
                    <Send className="h-4 w-4 ml-2" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Envoyer</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <div className="text-[11px] text-muted-foreground mt-1 pl-1">
            {usingServer ? "Connecté au serveur (SSE)." : "Mode démonstration: réponses simulées en local (aucun appel serveur)."}
          </div>
        </div>
      </footer>
    </div>
  );
}