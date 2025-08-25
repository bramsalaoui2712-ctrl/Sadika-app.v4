/* Frontend-only mock layer for AI chat until backend/LLM integration.
   - simulateAIResponse: token-by-token streaming simulation with delays
   - seedMessages: initial greeting and tips
   - quickPrompts: tappable suggestions to kick off a chat
*/

export const seedMessages = [
  {
    id: "sys-hello",
    role: "assistant",
    content:
      "Salut ! Je suis ton IA. Dis-moi ce que tu veux et je t'aide. Tu peux aussi utiliser le micro pour parler.",
    ts: Date.now(),
  },
];

export const quickPrompts = [
  "Résume cet article à partir d'un lien",
  "Prépare un message pro via WhatsApp",
  "Fais-moi une liste de courses",
  "Explique-moi ce concept simplement",
];

// Very simple, local-only AI simulation. No network calls.
// Calls onToken(tokenSoFar) repeatedly to emulate streaming.
export async function simulateAIResponse(userText, onToken = () => {}) {
  const baseReplies = [
    "Bonne question !",
    "Voici une réponse claire: ",
    "En résumé, ",
    "Tu peux aussi essayer ceci: ",
  ];
  // Create a lightweight reply based on user input
  const reply =
    (userText || "").trim().length < 4
      ? "Je t'écoute. Donne-moi un peu plus de contexte."
      : `${baseReplies[Math.floor(Math.random() * baseReplies.length)]} ${
          userText.length > 140
            ? "Je vais condenser l'essentiel pour toi."
            : ""
        }\n\n${
          userText
        }\n\nSi tu veux, je peux détailler, simplifier, ou donner des exemples.`;

  const tokens = reply.split(/(\s+)/); // include spaces to feel more real

  let acc = "";
  for (let i = 0; i &lt; tokens.length; i++) {
    const t = tokens[i];
    acc += t;
    onToken(acc);
    // variable delay for a more organic feeling
    const delay = 12 + Math.random() * 28;
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) =&gt; setTimeout(r, delay));
  }
  return acc;
}