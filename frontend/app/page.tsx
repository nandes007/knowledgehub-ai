import { ChatPanel } from "@/components/ChatPanel";
import { Sidebar } from "@/components/Sidebar";

export default function Home() {
  return (
    <div className="flex flex-1">
      <Sidebar />
      <ChatPanel />
    </div>
  );
}
