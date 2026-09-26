"""Server cuc bo cho live demo: phuc vu ui/dashboard.html va API chat RAG.

    python script/serve_dashboard.py            # http://127.0.0.1:8765
    python script/serve_dashboard.py --open     # mo trinh duyet luon

API:
    GET  /api/health -> trang thai LLM (provider, model, co API key chua)
    POST /api/chat   -> {"question": str, "states": ["baseline", "corrupted", "repaired"]}

Moi state doc dung collection ChromaDB cua state do, retrieval bang `answer_question`
(giong luc evaluation), roi LLM tra loi chi dua tren context da truy xuat.
Neu chua co API key, tra ve cau tra loi trich xuat cua `answer_question`.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import webbrowser

from core.config import Settings, load_settings, normalized_provider, require_llm_credentials
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm
from retrieval.qa import answer_question

MAX_QUESTION_CHARS = 500
PROMPT = """You answer questions about a small corpus of scholarly papers indexed from Crossref.
Use ONLY the context below. If the context does not contain the answer, say that the indexed corpus does not contain it.
Answer in the same language as the question, in at most 120 words, and cite the paper_id you used in square brackets.

Context:
{context}

Question: {question}"""


class ChatService:
    def __init__(self, settings: Settings):
        self.settings = settings
        paths = settings.paths
        self.embeddings = {
            "baseline": paths.embeddings_json,
            "corrupted": paths.corrupted_embeddings_json,
            "repaired": paths.repaired_embeddings_json,
        }
        self._indexes: dict[str, LocalEmbeddingIndex] = {}
        self._lock = threading.Lock()
        self._llm = None
        try:
            require_llm_credentials(settings)
            self.llm_ready, self.llm_reason = True, None
        except RuntimeError as exc:
            self.llm_ready, self.llm_reason = False, str(exc)

    def health(self) -> dict:
        return {
            "ok": True,
            "provider": normalized_provider(self.settings),
            "model": self.settings.model_name,
            "llm_ready": self.llm_ready,
            "reason": self.llm_reason,
            "states": [s for s, p in self.embeddings.items() if p.exists()],
            "top_k": self.settings.top_k,
        }

    def index(self, state: str) -> LocalEmbeddingIndex:
        with self._lock:
            if state not in self._indexes:
                self._indexes[state] = LocalEmbeddingIndex.load(self.settings, self.embeddings[state])
            return self._indexes[state]

    def llm(self):
        with self._lock:
            if self._llm is None:
                self._llm = build_llm(self.settings, temperature=0.0)
            return self._llm

    def ask(self, question: str, state: str) -> dict:
        started = time.perf_counter()
        index = self.index(state)
        scores = {r.paper_id: r.score for r in index.search(question)}
        result = answer_question(question, self.settings, index)
        payload = {
            "state": state,
            "answer": result.answer,
            "mode": "extractive",
            "model": None,
            "warning": None if self.llm_ready else self.llm_reason,
            "retrieved": [
                {"paper_id": pid, "title": title, "score": round(scores.get(pid, 1.0), 4)}
                for pid, title in zip(result.retrieved_doc_ids, result.retrieved_titles, strict=False)
            ],
        }
        if self.llm_ready and result.retrieved_contexts:
            context = "\n\n".join(
                f"[{pid}]\n{ctx[:1500]}" for pid, ctx in zip(result.retrieved_doc_ids, result.retrieved_contexts, strict=False)
            )
            try:
                message = self.llm().invoke(PROMPT.format(context=context, question=question))
                payload.update(answer=_text(message.content).strip(), mode="llm", model=self.settings.model_name)
            except Exception as exc:  # noqa: BLE001 - loi LLM khong duoc lam hong demo
                payload["warning"] = f"LLM lỗi, dùng câu trả lời trích xuất: {type(exc).__name__}: {exc}"[:300]
        payload["latency_ms"] = round((time.perf_counter() - started) * 1000)
        return payload


def _text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        parts.append(part.get("text", "") if isinstance(part, dict) else str(part))
    return "".join(parts)


def make_handler(service: ChatService, page_path):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self) -> None:
            # Chi cho phep same-origin va trang mo tu file:// (Origin: null), khong mo cho moi website.
            if self.headers.get("Origin") == "null":
                self.send_header("Access-Control-Allow-Origin", "null")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/dashboard.html", "/index.html"):
                self._send(200, page_path.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self._json(200, service.health())
            else:
                self._json(404, {"error": "Không tìm thấy"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/chat":
                self._json(404, {"error": "Không tìm thấy"})
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "Body phải là JSON"})
                return
            question = str(body.get("question") or "").strip()
            states = [s for s in body.get("states") or ["baseline"] if s in service.embeddings]
            if not question or len(question) > MAX_QUESTION_CHARS:
                self._json(400, {"error": f"Câu hỏi phải có 1–{MAX_QUESTION_CHARS} ký tự"})
                return
            if not states:
                self._json(400, {"error": "states phải thuộc baseline, corrupted, repaired"})
                return
            try:
                with ThreadPoolExecutor(max_workers=len(states)) as pool:
                    answers = list(pool.map(lambda s: service.ask(question, s), states))
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"[:300]})
                return
            self._json(200, {"question": question, "answers": answers})

        def log_message(self, fmt: str, *args) -> None:
            if "/api/chat" in (args[0] if args else ""):
                print(f"[serve] {self.address_string()} {fmt % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Live demo server cho dashboard THTrueMi")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Mở trình duyệt sau khi server sẵn sàng")
    args = parser.parse_args()

    settings = load_settings()
    service = ChatService(settings)
    page_path = settings.paths.project_dir / "ui" / "dashboard.html"

    print("[serve] Đang nạp 3 collection ChromaDB và model embedding...")
    for state in service.health()["states"]:
        service.index(state)
    h = service.health()
    llm = f"{h['provider']} · {h['model']}" if h["llm_ready"] else f"chưa sẵn sàng ({h['reason']}), dùng câu trả lời trích xuất"
    url = f"http://127.0.0.1:{args.port}"
    print(f"[serve] LLM: {llm}")
    print(f"[serve] Dashboard: {url}  (Ctrl+C để dừng)")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(service, page_path))
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] Đã dừng.")


if __name__ == "__main__":
    main()
