import { describe, expect, it } from "vitest";
import { createElement } from "react";
import {
  Button,
  Card,
  Input,
  Label,
  StatusStamp,
  StatusPill,
  Wordmark,
  BarChart,
} from "./ui";

describe("UI primitives", () => {
  describe("Button", () => {
    it("renders default primary variant", () => {
      const el = Button({ children: "Click me" });
      expect(el.props.className).toContain("bg-gold");
      expect(el.props.className).toContain("text-surface-primary");
      expect(el.props.className).toContain("focus-visible:ring-gold");
      expect(el.props.children).toBe("Click me");
    });

    it("renders secondary variant", () => {
      const el = Button({ variant: "secondary", children: "Secondary" });
      expect(el.props.className).toContain("border-border");
      expect(el.props.className).toContain("text-text-primary");
    });

    it("renders ghost variant", () => {
      const el = Button({ variant: "ghost", children: "Ghost" });
      expect(el.props.className).toContain("text-text-secondary");
    });

    it("renders danger variant", () => {
      const el = Button({ variant: "danger", children: "Delete" });
      expect(el.props.className).toContain("text-status-void");
    });

    it("merges custom className and disabled state", () => {
      const el = Button({ disabled: true, className: "custom-class" });
      expect(el.props.className).toContain("custom-class");
      expect(el.props.className).toContain("disabled:opacity-50");
      expect(el.props.disabled).toBe(true);
    });
  });

  describe("Card", () => {
    it("renders raised surface with rounded-xl and border", () => {
      const el = Card({ children: "Content" });
      expect(el.props.className).toContain("bg-surface-raised");
      expect(el.props.className).toContain("border-border");
      expect(el.props.className).toContain("rounded-xl");
    });
  });

  describe("Input", () => {
    it("renders with h-10, bg-surface-input, and gold focus ring", () => {
      const el = Input({ placeholder: "Type here" });
      expect(el.props.className).toContain("h-10");
      expect(el.props.className).toContain("bg-surface-input");
      expect(el.props.className).toContain("focus:ring-gold");
      expect(el.props.className).toContain("focus:border-gold");
      expect(el.props.placeholder).toBe("Type here");
    });
  });

  describe("Label", () => {
    it("renders text-secondary label", () => {
      const el = Label({ children: "Email" });
      expect(el.props.className).toContain("text-text-secondary");
      expect(el.props.children).toBe("Email");
    });
  });

  describe("StatusStamp and StatusPill", () => {
    it("exports StatusPill as an alias of StatusStamp", () => {
      expect(StatusPill).toBe(StatusStamp);
    });

    it("renders ready status with green style and Filed text", () => {
      const el = StatusStamp({ status: "ready" });
      expect(el.props.className).toContain("text-status-ready");
      expect(el.props.className).toContain("bg-status-ready-bg");
      expect(el.props.children).toBe("Filed");
    });

    it("renders processing status with pending style and Processing text", () => {
      const el = StatusStamp({ status: "processing" });
      expect(el.props.className).toContain("text-status-pending");
      expect(el.props.className).toContain("bg-status-pending-bg");
      expect(el.props.children).toBe("Processing");
    });

    it("renders failed status with void style and Void text", () => {
      const el = StatusStamp({ status: "failed" });
      expect(el.props.className).toContain("text-status-void");
      expect(el.props.className).toContain("bg-status-void-bg");
      expect(el.props.children).toBe("Void");
    });
  });

  describe("Wordmark", () => {
    it("renders full Wordmark with gold K and nowledgeHub", () => {
      const el = Wordmark({});
      expect(el.props.className).toContain("font-sans");
      const [kSpan, rest] = el.props.children;
      expect(kSpan.props.className).toContain("text-gold");
      expect(kSpan.props.children).toBe("K");
      expect(rest).toBe("nowledgeHub");
    });

    it("renders collapsed Wordmark with only K", () => {
      const el = Wordmark({ collapsed: true });
      const [kSpan, rest] = el.props.children;
      expect(kSpan.props.children).toBe("K");
      expect(rest).toBe(false);
    });
  });

  describe("BarChart", () => {
    it("renders empty message when no data", () => {
      const el = BarChart({ data: [], emptyMessage: "No data available." });
      expect(el.props.children).toBe("No data available.");
    });

    it("renders bar chart items with gold bars", () => {
      const data = [
        { label: "Day 1", value: 10 },
        { label: "Day 2", value: 20 },
      ];
      const el = BarChart({ data });
      expect(el.type).toBe("ul");
      expect(el.props.children).toHaveLength(2);
    });
  });
});
