import type { Metadata } from "next";
import { Geist, Geist_Mono, Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import { ThemeProvider } from "./theme-provider";
import "./globals.css";
import "./warm-design.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GST Saathi",
  description:
    "Paste or upload a GST notice and get a plain-language explanation of what it means, why you got it, and what to do next.",
};

// Runs before hydration to apply the saved/system theme class without a flash.
// An inline <script dangerouslySetInnerHTML> runs synchronously while the
// browser parses <head>, before any paint (see the official "preventing flash
// before hydration" guide). It replaces next/script (beforeInteractive), which
// a browser extension was injecting a second <script> next to and causing a
// hydration mismatch. suppressHydrationWarning makes React accept the DOM.
const THEME_SCRIPT = `(function(){
  try {
    var stored = localStorage.getItem("gst-theme");
    var dark = stored === "dark" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
  } catch (e) {}
})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} ${jakarta.variable}`}
      // Next.js/the dev overlay can produce a different className string on
      // the client than the server rendered (font-variable class names), so
      // suppress the resulting hydration warning on this element.
      suppressHydrationWarning
    >
      <head>
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }}
        />
      </head>
      <body className="font-sans">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
