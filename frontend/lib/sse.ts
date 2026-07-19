export type SseEvent = { event: string; data: string };

function parseSseBlock(block: string): SseEvent {
  const lines = block.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLine = lines.find((line) => line.startsWith("data: "));
  return {
    event: eventLine?.slice("event: ".length) ?? "",
    data: dataLine?.slice("data: ".length) ?? "",
  };
}

// Reads the response body as it arrives, yielding each event as soon as its
// blank-line terminator shows up (rather than buffering the whole stream).
export async function* parseSseStream(response: Response): AsyncGenerator<SseEvent> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Response has no readable body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (block.trim()) yield parseSseBlock(block);
    }

    if (done) break;
  }

  if (buffer.trim()) yield parseSseBlock(buffer);
}
