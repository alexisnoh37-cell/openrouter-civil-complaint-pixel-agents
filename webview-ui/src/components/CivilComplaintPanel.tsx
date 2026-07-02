import { useMemo, useState } from 'react';

import { Button } from './ui/Button.js';

const AGENTS = [
  ['classification', '분류 에이전트', 'Read'],
  ['jurisdiction', '소관판단 에이전트', 'Read'],
  ['similar_search', '유사민원검색 에이전트', 'Read'],
  ['draft', '초안작성 에이전트', 'Write'],
  ['expression_review', '표현검토 에이전트', 'Read'],
  ['missing_question_review', '누락질문검토 에이전트', 'Read'],
  ['privacy_review', '개인정보검토 에이전트', 'Read'],
] as const;

type AgentStatus = 'waiting' | 'running' | 'completed' | 'error';

interface StreamEvent {
  agent: string;
  label?: string;
  status: AgentStatus;
  message?: string;
  result?: Record<string, unknown>;
}

interface FinalResult {
  final_status?: string;
  final_draft?: string;
  review_results?: Record<string, unknown>;
}

function emitPixelMessage(message: Record<string, unknown>): void {
  window.dispatchEvent(new CustomEvent('pixel-agent-message', { detail: message }));
}

function parseSseChunk(buffer: string): { events: StreamEvent[]; remainder: string } {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const remainder = blocks.pop() ?? '';
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n');
    if (!data) continue;
    events.push(JSON.parse(data) as StreamEvent);
  }
  return { events, remainder };
}

export function CivilComplaintPanel() {
  const [isOpen, setIsOpen] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [backendUrl, setBackendUrl] = useState('http://127.0.0.1:8000');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<FinalResult | null>(null);
  const [statuses, setStatuses] = useState<Record<string, AgentStatus>>(
    Object.fromEntries(AGENTS.map(([key]) => [key, 'waiting'])),
  );

  const completedCount = useMemo(
    () => Object.values(statuses).filter((status) => status === 'completed').length,
    [statuses],
  );

  const resetAgents = () => {
    for (let index = 0; index < AGENTS.length; index++) {
      const id = index + 1;
      emitPixelMessage({ type: 'agentClosed', id });
      emitPixelMessage({ type: 'agentCreated', id, folderName: AGENTS[index][1] });
      emitPixelMessage({ type: 'agentStatus', id, status: 'waiting', awaitingInput: true });
    }
    setStatuses(Object.fromEntries(AGENTS.map(([key]) => [key, 'waiting'])));
  };

  const applyAgentEvent = (event: StreamEvent) => {
    if (event.agent === 'final') {
      setResult((event.result ?? {}) as FinalResult);
      return;
    }
    const index = AGENTS.findIndex(([key]) => key === event.agent);
    if (index < 0) return;

    const id = index + 1;
    const [, label, toolName] = AGENTS[index];
    const toolId = `civil-${event.agent}`;
    setStatuses((previous) => ({ ...previous, [event.agent]: event.status }));

    if (event.status === 'running') {
      emitPixelMessage({ type: 'agentStatus', id, status: 'active' });
      emitPixelMessage({
        type: 'agentToolStart',
        id,
        toolId,
        toolName,
        status: event.message || `${label} 진행 중`,
      });
    } else if (event.status === 'completed' || event.status === 'error') {
      emitPixelMessage({ type: 'agentToolDone', id, toolId });
      emitPixelMessage({ type: 'agentStatus', id, status: 'waiting', awaitingInput: false });
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || running) return;

    setRunning(true);
    setError('');
    setResult(null);
    resetAgents();

    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${backendUrl.replace(/\/$/, '')}/process/file/stream`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok || !response.body) {
        throw new Error(`백엔드 응답 오류 (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const parsed = parseSseChunk(buffer);
        buffer = parsed.remainder;
        parsed.events.forEach(applyAgentEvent);
        if (done) break;
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '민원 처리 중 오류가 발생했습니다.');
    } finally {
      setRunning(false);
    }
  };

  if (!isOpen) {
    return (
      <Button
        variant="accent"
        onClick={() => setIsOpen(true)}
        className="absolute top-10 left-10 z-30 bg-accent hover:bg-accent-bright"
      >
        민원 분석
      </Button>
    );
  }

  return (
    <section className="civil-panel pixel-panel absolute top-10 left-10 z-30 w-360 max-h-[calc(100%-20px)] overflow-y-auto p-12">
      <div className="flex items-center justify-between gap-8 mb-10">
        <div>
          <div className="text-xs text-text-muted">OPENROUTER AGENT OFFICE</div>
          <h1 className="text-xl m-0">민원 처리 MVP</h1>
        </div>
        <button
          type="button"
          className="text-lg text-text-muted bg-transparent border-0 cursor-pointer"
          title="패널 닫기"
          onClick={() => setIsOpen(false)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-8">
        <label className="text-sm">
          민원 파일
          <input
            className="civil-input mt-4 w-full"
            type="file"
            accept=".txt,.md,.csv,.xlsx,.xls"
            required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="text-sm">
          백엔드 주소
          <input
            className="civil-input mt-4 w-full"
            value={backendUrl}
            onChange={(event) => setBackendUrl(event.target.value)}
          />
        </label>
        <Button variant="accent" disabled={!file || running} className="w-full justify-center">
          {running ? `분석 중 ${completedCount}/7` : '분석 및 초안 생성'}
        </Button>
      </form>

      <div className="grid grid-cols-2 gap-4 mt-10">
        {AGENTS.map(([key, label]) => (
          <div key={key} className={`civil-status civil-status-${statuses[key]}`}>
            <span>{label.replace(' 에이전트', '')}</span>
            <strong>{statuses[key]}</strong>
          </div>
        ))}
      </div>

      {error && <p className="civil-error mt-10">{error}</p>}
      {result && (
        <div className="civil-result mt-10">
          <div className="text-sm text-status-success mb-6">
            {result.final_status || '처리 완료'}
          </div>
          <div className="text-sm whitespace-pre-wrap leading-relaxed">
            {result.final_draft || '생성된 초안이 없습니다.'}
          </div>
        </div>
      )}
    </section>
  );
}
