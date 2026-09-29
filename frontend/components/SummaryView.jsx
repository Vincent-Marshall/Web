"use client";

// 页面总结模块。
// 交互流：粘贴链接 → POST /api/summary（正文提取 + 模型结构化摘要）→ 结果卡片；
// 历史列表加载时拉取一次，可点击查看已有摘要的原文。
import { useEffect, useState } from "react";
import Nav from "./Nav.jsx";
import PageHeading from "./PageHeading.jsx";
import AnimatedCardGrid from "./AnimatedCardGrid.jsx";

const API = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function SummaryView() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory() {
    try {
      const res = await fetch(`${API}/api/summary/history`);
      if (res.ok) setHistory(await res.json());
    } catch {
      /* 历史加载失败不阻塞主功能 */
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API}/api/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `摘要失败：${res.status}`);
      }
      setResult(await res.json());
      loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AnimatedCardGrid className="dashboard-grid">
      <article className="hero-stage panel-full">
        <Nav />
        <PageHeading
          title="页面总结"
          subtitle="粘贴任意文章链接，一键生成结构化摘要"
        />
      </article>

      <article className="panel panel-half lab-panel card">
        <div className="panel-heading">
          <p className="section-kicker">输入区</p>
          <h3>文章链接</h3>
        </div>
        <form className="summary-form" onSubmit={handleSubmit}>
          <label htmlFor="url-input">网址（http/https）</label>
          <input
            id="url-input"
            type="url"
            placeholder="https://example.com/article/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
          {error && <p className="lab-error">{error}</p>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "总结中…" : "一键总结"}
          </button>
        </form>
      </article>

      <article className="panel panel-half lab-panel card">
        <div className="panel-heading">
          <p className="section-kicker">结果区</p>
          <h3>结构化摘要</h3>
        </div>
        {result ? (
          <div className="summary-result">
            <p className="summary-title">
              <a href={result.url} target="_blank" rel="noreferrer">
                {result.title}
              </a>
            </p>
            <div className="summary-block">
              <h4>核心观点</h4>
              <p>{result.gist}</p>
            </div>
            <div className="summary-block">
              <h4>要点</h4>
              <ul className="summary-points">
                {result.points.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
            {result.quote && result.quote !== "无" && (
              <div className="summary-block">
                <h4>金句</h4>
                <p className="summary-quote">「{result.quote}」</p>
              </div>
            )}
          </div>
        ) : (
          <p className="digest-empty">摘要结果会显示在这里</p>
        )}
      </article>

      {history.length > 0 && (
        <article className="panel panel-full card">
          <div className="panel-heading">
            <p className="section-kicker">历史</p>
            <h3>最近总结</h3>
          </div>
          {history.map((h) => (
            <div key={h.created_at} className="summary-history-item">
              <a href={h.url} target="_blank" rel="noreferrer">
                {h.title}
              </a>
              <p>{h.gist}</p>
            </div>
          ))}
        </article>
      )}
    </AnimatedCardGrid>
  );
}
