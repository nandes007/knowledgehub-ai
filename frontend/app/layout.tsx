import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://knowledgehubai.nandes.tech"),
  title: "KnowledgeHub AI",
  description:
    "A self-hostable AI knowledge assistant for teams with RAG, hybrid search, and source citations.",
  openGraph: {
    title: "KnowledgeHub AI",
    description:
      "A self-hostable AI knowledge assistant for teams with RAG, hybrid search, and source citations.",
    url: "https://knowledgehubai.nandes.tech",
    siteName: "KnowledgeHub AI",
    images: [
      {
        url: "/knowledgehub-og.png",
        width: 1200,
        height: 630,
        alt: "KnowledgeHub AI — AI-powered knowledge assistant for teams",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "KnowledgeHub AI",
    description:
      "A self-hostable AI knowledge assistant for teams with RAG, hybrid search, and source citations.",
    images: ["/knowledgehub-og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
      // ponytail: browser extensions (Dark Reader) inject attrs on <html> before hydration
      suppressHydrationWarning
    >
      <body className="h-full flex flex-col font-sans">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
