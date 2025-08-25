import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ScrollArea } from "../components/ui/scroll-area";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Card } from "../components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Mic, MicOff, Send, Volume2, VolumeX, Sparkles, Settings } from "lucide-react";
import ChatMessage from "../components/ChatMessage";
import { seedMessages, quickPrompts } from "../mock/mock";
import { useToast } from "../hooks/use-toast";
import { Slider } from "../components/ui/slider";

const SESSION_KEY = "chat.session.id";
const MESSAGES_KEY = "chat.messages";
const TTS_KEY = "chat.tts";
const KERNEL_MODE_KEY = "kernel.mode";
const KERNEL_COUNCIL_KEY = "kernel.council";
const KERNEL_TRUTH_KEY = "kernel.truth";
const HYBRID_KEY = "hybrid.on";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = BACKEND_URL ? `${BACKEND_URL}/api` : undefined;

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
    if (saved) { try { return JSON.parse(saved); } catch {} }
    return seedMessages;
  });

  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [tts, setTts] = useState(() => localStorage.getItem(TTS_KEY) === "1");
  const [usingServer, setUsingServer] = useState(false);

  // kernel/hybride settings
  const [kernelMode, setKernelMode] = useState(() => localStorage.getItem(KERNEL_MODE_KEY) || "public");
  const [kernelCouncil, setKernelCouncil] = useState(() => parseInt(localStorage.getItem(KERNEL_COUNCIL_KEY) || "1", 10));
  const [kernelTruth, setKernelTruth] = useState(() => (localStorage.getItem(KERNEL_TRUTH_KEY) || "1") === "1");
  const [hybridOn, setHybridOn] = useState(() => (localStorage.getItem(HYBRID_KEY) || "1") === "1");
  const [showSettings, setShowSettings] = useState(false);

  const recognitionRef = useRef(null);
  const speakingRef = useRef(false);

  // Persist
  useEffect(() => { localStorage.setItem(MESSAGES_KEY, JSON.stringify(messages)); }, [messages]);
  useEffect(() => { localStorage.setItem(TTS_KEY, tts ? "1" : "0"); }, [tts]);
  useEffect(() => { localStorage.setItem(KERNEL_MODE_KEY, kernelMode); }, [kernelMode]);
  useEffect(() => { localStorage.setItem(KERNEL_COUNCIL_KEY, String(kernelCouncil)); }, [kernelCouncil]);
  useEffect(() => { localStorage.setItem(KERNEL_TRUTH_KEY, kernelTruth ? "1" : "0"); }, [kernelTruth]);
  useEffect(() => { localStorage.setItem(HYBRID_KEY, hybridOn ? "1" : "0"); }, [hybridOn]);

  useEffect(() => { getSessionId(); }, []);

  const onSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg = { id: `m-${Date.now()}`, role: "user", content: text, ts: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");

    const asstId = `a-${Date.now()}`;
    const asstMsg = { id: asstId, role: "assistant", content: "", ts: Date.now() };
    setMessages((m) => [...m, asstMsg]);

    if (!API) {
      toast({ title: "Backend absent", description: "REACT_APP_BACKEND_URL manquant. Mock local utilisé." });
      const { simulateAIResponse } = await import("../mock/mock");
      try {
        await simulateAIResponse(text, (acc) => {
          setMessages((m) => m.map((mm) => (mm.id === asstId ? { ...mm, content: acc } : mm)));
        });
      } catch (e) { toast({ title: "Erreur", description: "La réponse (mock) a échoué." }); }
      return;
    }

    try {
      const sid = getSessionId();
      const qs = new URLSearchParams({
        q: text,
        sessionId: sid,
        provider: hybridOn ? "hybrid" : "kernel",
        model: hybridOn ? "gpt-4o-mini" : "local",
        mode: kernelMode || "public",
        council: String(Math.max(1, Math.min(5, kernelCouncil || 1))),
        truth: kernelTruth ? "1" : "0",
        strict_identity: "1",
        refusal_handling: "1",
      });
      const url = `${API}/chat/stream?${qs.toString()}`;
      const es = new EventSource(url);
      setUsingServer(true);

      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "content") {
            const acc = data.content || "";
            setMessages((m) => m.map((mm) => (mm.id === asstId ? { ...mm, content: (mm.content || "") + acc } : mm)));
          } else if (data.type === "complete") {
            es.close();
            if (tts && "speechSynthesis" in window && !speakingRef.current) {
              const msg = (prev => prev.find((x) => x.id === asstId)?.content)(messages);
              const finalText = msg || document.querySelector(`[data-mid="${asstId}"]`)?.textContent || "";
              if (finalText) {
                speakingRef.current = true;
                const utter = new SpeechSynthesisUtterance(finalText);
                utter.lang = "fr-FR"; utter.rate = 1; utter.onend = () => { speakingRef.current = false; };
                window.speechSynthesis.cancel(); window.speechSynthesis.speak(utter);
              }
            }
          }
        } catch {}
      };

      es.onerror = () => { try { es.close(); } catch {}; };
    } catch (e) {
      console.error(e);
      toast({ title: "Erreur", description: "La requête SSE a échoué." });
    }
  }, [API, input, tts, toast, messages, kernelMode, kernelCouncil, kernelTruth, hybridOn]);

  const Header = useMemo(() => (
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
          <Button variant="secondary" size="icon" onClick={() => setShowSettings((s)=>!s)}>
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {showSettings && (
        <div className="max-w-screen-sm mx-auto px-4 pb-3">
          <Card className="p-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-center">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-muted-foreground">Mode</span>
                <div className="flex gap-2">
                  <Button size="sm" variant={kernelMode==='public'? 'default':'secondary'} onClick={()=>setKernelMode('public')}>Public</Button>
                  <Button size="sm" variant={kernelMode==='private'? 'default':'secondary'} onClick={()=>setKernelMode('private')}>Privé</Button>
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm text-muted-foreground mb-1">
                  <span>Conseil (variantes)</span>
                  <span>{kernelCouncil}</span>
                </div>
                <Slider value={[kernelCouncil]} min={1} max={5} step={1} onValueChange={(v)=>setKernelCouncil(v[0])} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Cercle de Vérité</span>
                <Switch checked={kernelTruth} onCheckedChange={setKernelTruth} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Hybride (noyau + LLM)</span>
                <Switch checked={hybridOn} onCheckedChange={setHybridOn} />
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  ), [tts, showSettings, kernelMode, kernelCouncil, kernelTruth, hybridOn]);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {Header}
      <main className="flex-1">
        <div className="max-w-screen-sm mx-auto px-3 pb-28 pt-3">
          <Card className="p-3 mb-3">
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((q, idx) => (
                <Badge key={idx} variant="secondary" className="cursor-pointer hover:opacity-90" onClick={() => setInput(q)}>
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
            <Button size="icon" variant={listening ? "destructive" : "secondary"} className="shrink-0" onClick={()=>setListening((s)=>!s)}>
              {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>
            <Textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Écris ou dicte ton message..." className="min-h-[44px] max-h-[132px] resize-y" />
            <Button onClick={onSend} disabled={!input.trim()} className="shrink-0">
              Envoyer
              <Send className="h-4 w-4 ml-2" />
            </Button>
          </div>
          <div className="text-[11px] text-muted-foreground mt-1 pl-1">
            {usingServer ? (hybridOn ? `Hybride (LLM sous contrôle du noyau) — SSE.` : `Kernel pur — SSE.`) : "Mode démonstration: réponses simulées en local (aucun appel serveur)."}
          </div>
        </div>
      </footer>
    </div>
  );
}