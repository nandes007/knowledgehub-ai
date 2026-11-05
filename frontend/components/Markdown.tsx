import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { isProtectedPath } from "@/lib/api";
import { AuthImage } from "./AuthImage";

// Wide tables scroll inside the bubble instead of stretching the chat on small screens.
const markdownComponents: Components = {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- drop `node` so it is not spread onto the DOM
  table: ({ node, ...props }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border">
      <table {...props} />
    </div>
  ),
  // Document pictures in answers are API paths behind auth.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- drop `node` so it is not spread onto the DOM
  img: ({ node, src, alt, ...props }) =>
    typeof src === "string" && isProtectedPath(src) ? (
      <AuthImage src={src} alt={alt ?? ""} className="min-h-24 min-w-40" />
    ) : (
      // eslint-disable-next-line @next/next/no-img-element -- data URIs can't go through next/image
      <img src={src} alt={alt} {...props} />
    ),
};

// Embedded DOCX/PPTX images arrive as base64 data URIs, which react-markdown strips by default.
// Allow raster images only; every other URL keeps the default sanitizing.
function urlTransform(url: string): string {
  return /^data:image\/(png|jpe?g|gif|webp|bmp);base64,/i.test(url) ? url : defaultUrlTransform(url);
}

export function Markdown({ children, className = "" }: { children: string; className?: string }) {
  return (
    <div className={`prose-dark text-sm leading-relaxed text-text-primary [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:rounded-md [&_code]:bg-border [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-gold [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-surface-raised [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_a]:text-gold [&_a]:underline [&_strong]:text-text-primary [&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_blockquote]:border-l-2 [&_blockquote]:border-gold/30 [&_blockquote]:pl-3 [&_blockquote]:text-text-secondary [&_table]:w-full [&_table]:border-collapse [&_th]:bg-surface-raised [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_th]:whitespace-nowrap [&_td]:border-t [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_del]:text-text-secondary [&_img]:my-3 [&_img]:max-w-full [&_img]:rounded-lg [&_img]:border [&_img]:border-border ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents} urlTransform={urlTransform}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
