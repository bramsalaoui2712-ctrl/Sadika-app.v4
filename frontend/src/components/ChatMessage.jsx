import React from "react";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Card } from "../components/ui/card";
import { cn } from "../lib/utils";
import { Bot, UserRound } from "lucide-react";

// Small util if lib/utils doesn't exist; fallback to simple join
function cx(...args) {
  return args.filter(Boolean).join(" ");
}

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={cx("w-full flex gap-3", isUser ? "justify-end" : "justify-start")}> 
      {!isUser &amp;&amp; (
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-secondary text-secondary-foreground">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}

      <Card
        className={cx(
          "max-w-[78%] px-3 py-2 text-sm leading-relaxed shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground rounded-2xl rounded-br-sm"
            : "bg-muted text-foreground rounded-2xl rounded-bl-sm"
        )}
      >
        <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
      </Card>

      {isUser &amp;&amp; (
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-primary text-primary-foreground">
            <UserRound className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}