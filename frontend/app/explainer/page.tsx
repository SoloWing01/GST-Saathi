import SiteHeader from "../components/site-header";
import SiteFooter from "../components/site-footer";
import UploadClient from "../upload-client";

export const metadata = {
  title: "Explainer — GST Saathi",
  description:
    "Paste or upload a GST notice and get a plain-language explanation of what it means, why you got it, and what to do next.",
};

export default function ExplainerPage() {
  return (
    <main className="min-h-screen flex flex-col">
      <SiteHeader />

      <div className="flex-1 px-6 py-12">
        <div className="max-w-2xl mx-auto w-full">
          <div className="mb-8 animate-fade-in">
            <h1 className="text-2xl font-display font-semibold text-ink tracking-tight">
              What does your notice say?
            </h1>
            <p className="text-ink-muted mt-2 text-[15px] leading-relaxed max-w-lg">
              Choose <strong>paste text</strong> or <strong>upload a file</strong>. We&apos;ll
              explain what it means, why you got it, and what to do next.
            </p>
          </div>

          <UploadClient />
        </div>
      </div>

      <SiteFooter />
    </main>
  );
}
