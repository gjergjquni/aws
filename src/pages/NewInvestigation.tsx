import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { analysisStages } from "@/data/agents";
import { analysisApi } from "@/services/analysisApi";
import { investigationsApi } from "@/services/investigationsApi";
import type { CreateInvestigationInput, InvestigationCategory } from "@/types";

type Stage = "form" | "analyzing" | "done";

function AnalyzingState({
  input,
  onComplete,
}: {
  input: CreateInvestigationInput;
  onComplete: (id: string) => void;
}) {
  const [step, setStep] = useState(0);

  const runAnalysis = useCallback(async () => {
    const result = await analysisApi.runAnalysis(input, (stageIndex) => {
      setStep(stageIndex + 1);
    });
    const created = await investigationsApi.create(input, result);
    onComplete(created.id);
  }, [input, onComplete]);

  useEffect(() => {
    runAnalysis();
  }, [runAnalysis]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[var(--accent)] text-[var(--primary)] mb-4">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.4" strokeDasharray="4 2" />
              <circle cx="11" cy="11" r="3.5" fill="currentColor" fillOpacity="0.3" stroke="currentColor" strokeWidth="1.4" />
              <circle cx="11" cy="5" r="1.5" fill="currentColor" />
              <circle cx="16.2" cy="14" r="1.5" fill="currentColor" fillOpacity="0.6" />
              <circle cx="5.8" cy="14" r="1.5" fill="currentColor" fillOpacity="0.6" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Analyzing Investigation</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">AI agents are reviewing the submitted evidence.</p>
        </div>

        <div className="space-y-4">
          {analysisStages.map((agent, i) => {
            const isDone = step > i;
            const isActive = step === i;
            return (
              <div
                key={agent.key}
                className={`flex items-start gap-3 p-4 rounded-[var(--radius-lg)] border transition-all duration-300 ${
                  isDone
                    ? 'border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20'
                    : isActive
                    ? 'border-[var(--primary)] bg-[var(--accent)]'
                    : 'border-[var(--border)] bg-[var(--card)] opacity-50'
                }`}
              >
                <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors ${
                  isDone ? 'bg-green-500 text-white' : isActive ? 'bg-[var(--primary)] text-white' : 'bg-[var(--border)] text-[var(--muted-foreground)]'
                }`}>
                  {isDone ? (
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  ) : isActive ? (
                    <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  ) : (
                    <span className="text-xs font-mono">{i + 1}</span>
                  )}
                </div>
                <div>
                  <div className={`text-sm font-medium ${isActive || isDone ? 'text-[var(--foreground)]' : 'text-[var(--muted-foreground)]'}`}>
                    {agent.label}
                  </div>
                  <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{agent.description}</div>
                  {isActive && (
                    <div className="mt-2 h-1 bg-[var(--border)] rounded-full overflow-hidden w-32">
                      <div className="h-full bg-[var(--primary)] rounded-full animate-[progress_1.4s_ease-in-out_forwards]" style={{ width: '70%' }} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <p className="text-center text-xs text-[var(--muted-foreground)] mt-8">
          Processing securely with Amazon Nova Pro
        </p>
      </div>
    </div>
  );
}

export default function NewInvestigation() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<Stage>("form");
  const [pendingInput, setPendingInput] = useState<CreateInvestigationInput | null>(null);
  const [form, setForm] = useState({
    claimId: `CLM-00${Math.floor(Math.random() * 90 + 10)}`,
    category: '',
    orderValue: '',
    explanation: '',
  });
  const [image, setImage] = useState<{ file: File; preview: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) return;
    const preview = URL.createObjectURL(file);
    setImage({ file, preview });
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.category) e.category = 'Select a product category';
    if (!form.orderValue || isNaN(Number(form.orderValue))) e.orderValue = 'Enter a valid order value';
    if (!form.explanation.trim() || form.explanation.length < 20) e.explanation = 'Provide a description of at least 20 characters';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const input: CreateInvestigationInput = {
      product: `Return claim — ${form.category}`,
      category: form.category as InvestigationCategory,
      orderValue: Number(form.orderValue),
      customerExplanation: form.explanation,
      imageUrl: image?.preview ?? null,
    };

    setPendingInput(input);
    setStage("analyzing");
  };

  if (stage === "analyzing" && pendingInput) {
    return (
      <AnalyzingState
        input={pendingInput}
        onComplete={(id) => navigate(`/investigations/${id}`)}
      />
    );
  }

  return (
    <div className="px-6 py-6 max-w-[720px] mx-auto">
      <div className="mb-7">
        <h2 className="text-xl font-semibold text-[var(--foreground)]">New Investigation</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Submit a return claim for AI-assisted investigation.</p>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {/* Claim Details */}
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 mb-5">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">1. Claim Details</h3>
          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Claim ID</label>
              <input
                type="text"
                value={form.claimId}
                readOnly
                className="w-full px-3 py-2 text-sm bg-[var(--muted)] border border-[var(--border)] rounded-[var(--radius)] text-[var(--muted-foreground)] font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Product Category <span className="text-red-500">*</span></label>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className={`w-full px-3 py-2 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.category ? 'border-red-400' : 'border-[var(--border)]'}`}
              >
                <option value="">Select…</option>
                <option value="electronics">Electronics</option>
                <option value="clothing">Clothing</option>
                <option value="home">Home & Garden</option>
                <option value="sporting">Sporting Goods</option>
                <option value="books">Books & Media</option>
              </select>
              {errors.category && <p className="text-xs text-red-500 mt-1">{errors.category}</p>}
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Order Value ($) <span className="text-red-500">*</span></label>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={form.orderValue}
                onChange={(e) => setForm({ ...form, orderValue: e.target.value })}
                className={`w-full px-3 py-2 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.orderValue ? 'border-red-400' : 'border-[var(--border)]'}`}
              />
              {errors.orderValue && <p className="text-xs text-red-500 mt-1">{errors.orderValue}</p>}
            </div>
          </div>
        </section>

        {/* Customer Explanation */}
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 mb-5">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-1">2. Customer Explanation</h3>
          <p className="text-xs text-[var(--muted-foreground)] mb-3">Paste the customer's description of the issue, verbatim.</p>
          <textarea
            placeholder="Enter the customer's explanation of why they are returning the product…"
            rows={5}
            value={form.explanation}
            onChange={(e) => setForm({ ...form, explanation: e.target.value })}
            className={`w-full px-3 py-2.5 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] resize-none ${errors.explanation ? 'border-red-400' : 'border-[var(--border)]'}`}
          />
          <div className="flex items-center justify-between mt-1">
            {errors.explanation ? (
              <p className="text-xs text-red-500">{errors.explanation}</p>
            ) : (
              <span />
            )}
            <span className="text-xs text-[var(--muted-foreground)]">{form.explanation.length} chars</span>
          </div>
        </section>

        {/* Visual Evidence */}
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 mb-5">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-1">3. Visual Evidence</h3>
          <p className="text-xs text-[var(--muted-foreground)] mb-3">Upload return evidence. Optional but improves analysis accuracy.</p>

          {image ? (
            <div className="relative">
              <img src={image.preview} alt="Upload preview" className="w-full rounded-[var(--radius)] object-cover max-h-60" />
              <button
                type="button"
                onClick={() => setImage(null)}
                className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center text-xs hover:bg-black/80"
              >
                ✕
              </button>
              <div className="mt-2 text-xs text-[var(--muted-foreground)] font-mono">{image.file.name}</div>
            </div>
          ) : (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
              onClick={() => fileRef.current?.click()}
              className={`flex flex-col items-center justify-center border-2 border-dashed rounded-[var(--radius-lg)] p-10 cursor-pointer transition-colors ${
                dragOver ? 'border-[var(--primary)] bg-[var(--accent)]' : 'border-[var(--border)] hover:border-[var(--primary)] hover:bg-[var(--accent)]'
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-[var(--muted)] flex items-center justify-center mb-3 text-[var(--muted-foreground)]">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 12V4M9 4L6 7M9 4L12 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M3 13.5V14a1.5 1.5 0 001.5 1.5h9A1.5 1.5 0 0015 14v-.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--foreground)]">Upload return evidence</p>
              <p className="text-xs text-[var(--muted-foreground)] mt-1">Drag & drop or click to select</p>
              <p className="text-[10px] text-[var(--muted-foreground)] mt-1">Supports JPEG, PNG</p>
            </div>
          )}
          <input ref={fileRef} type="file" accept="image/jpeg,image/png" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        </section>

        {/* Privacy */}
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 mb-6">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-[var(--primary)] flex-shrink-0">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L2 3.5V7.5C2 10.5 4.2 13 7 14C9.8 13 12 10.5 12 7.5V3.5L7 1Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
                <path d="M4.5 7L6 8.5L9.5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-medium text-[var(--foreground)]">Privacy Protection</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-0.5 leading-relaxed">
                Personal information will be automatically removed before AI processing. Customer data is anonymized and never shared with external services.
              </div>
            </div>
          </div>
        </section>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate('/investigations')}
            className="px-4 py-2 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-6 py-2.5 bg-[var(--primary)] text-white text-sm font-semibold rounded-[var(--radius)] hover:opacity-90 transition-opacity inline-flex items-center gap-2"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3" strokeDasharray="3 1.5" />
              <circle cx="7" cy="7" r="2" fill="currentColor" />
            </svg>
            Start Investigation
          </button>
        </div>
      </form>
    </div>
  );
}
