"use client";

// 科技早报页。
// 数据流：页面加载时 GET /api/news/today（今天没生成会回退最近一期）；
// 顶部日期选择器切历史期数；「立即生成一期」按钮触发后台任务，轮询 /status 直到完成。
import { useEffect, useState } from "react";
import Nav from "./Nav.jsx";
import PageHeading from "./PageHeading.jsx";
import AnimatedCardGrid from "./AnimatedCardGrid.jsx";

const API = process.env.NEXT_PUBLIC_API_BASE_URL;

const CATEGORY_META = {
  tech: { label: "科技", color: "#0071e3" },
  cn_politics: { label: "国内时政", color: "#b42318" },
  world_politics: { label: "国际时政", color: "#7a5af8" },
  world_life: { label: "国际生活", color: "#0a7d53" },
};

export default function NewsDigestView() {
  const [digest, setDigest] = useState(null);   // 当前展示的一期早报
  const [dates, setDates] = useState([]);       // 历史期数列表
  const [selected, setSelected] = useState(""); // 选中的日期（空 = 今天）
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");     // 手动生成的状态提示
  const [running, setRunning] = useState(false);

  async function loadDigest(date) {
    setError("");
    try {
      const url = date
        ? `${API}/api/news/digest?date=${encodeURIComponent(date)}`
        : `${API}/api/news/today`;
      const res = await fetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `加载失败：${res.status}`);
      }
      const data = await res.json();
      setDigest(data.digest ?? data);
      setSelected(date || data.date);
    } catch (e) {
      setError(e.message);
    }
  }

  async function loadArchive() {
    try {
      const res = await fetch(`${API}/api/news/archive`);
      if (res.ok) setDates((await res.json()).dates);
    } catch {
      /* 历史列表加载失败不影响主内容 */
    }
  }

  useEffect(() => {
    loadDigest("");
    loadArchive();
  }, []);

  async function handleRun() {
    setNotice("");
    try {
      const res = await fetch(`${API}/api/news/run`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `触发失败：${res.status}`);
      setRunning(true);
      setNotice("早报生成中，约需 1-2 分钟，完成后自动刷新…");
      pollStatus();
    } catch (e) {
      setNotice(e.message);
    }
  }

  function pollStatus() {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/news/status`);
        const s = await res.json();
        if (!s.running) {
          clearInterval(timer);
          setRunning(false);
          if (s.last && !s.last.error) {
            setNotice("生成完成！");
            loadDigest("");
            loadArchive();
          } else {
            setNotice(`生成失败：${s.last?.error || "未知错误"}`);
          }
        }
      } catch {
        /* 网络抖动继续轮询 */
      }
    }, 3000);
  }

  return (
    <AnimatedCardGrid className="dashboard-grid">
      <article className="hero-stage panel-full">
        <Nav />
        <PageHeading
          title="科技早报"
          subtitle="每天 9:00 自动聚合科技与时政新闻，AI 摘要后推送到邮箱"
        />
      </article>

      <article className="panel panel-full card digest-control">
        <div className="digest-control-row">
          <label>
            期数：
            <select
              value={selected}
              onChange={(e) => loadDigest(e.target.value)}
              className="digest-select"
            >
              <option value="">今天</option>
              {dates.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          {digest?.sent_at && (
            <span className="digest-sent">已发送邮件 · {digest.sent_at.slice(0, 16)}</span>
          )}
          <button className="primary-button" type="button" onClick={handleRun} disabled={running}>
            {running ? "生成中…" : "立即生成一期"}
          </button>
        </div>
        {notice && <p className="digest-notice">{notice}</p>}
        {error && <p className="lab-error">{error}</p>}
      </article>

      {digest?.sections?.map((section) => {
        const meta = CATEGORY_META[section.category] || { label: section.category, color: "#555" };
        return (
          <article key={section.category} className="panel panel-full card digest-section">
            <div className="panel-heading digest-heading">
              <span className="digest-tag" style={{ background: meta.color }}>
                {meta.label}
              </span>
              <span className="digest-count">{section.items.length} 条</span>
            </div>
            {section.items.map((it) => (
              <div key={it.url} className="digest-item">
                <h3>
                  <a href={it.url} target="_blank" rel="noreferrer">
                    {it.title}
                  </a>
                </h3>
                <p className="digest-gist">{it.ai_gist}</p>
                {it.ai_detail && <p className="digest-detail">{it.ai_detail}</p>}
                <p className="digest-src">
                  来源 {it.source}
                  {it.published_at ? ` · ${it.published_at.slice(0, 16)}` : ""}
                </p>
              </div>
            ))}
          </article>
        );
      })}

      {!digest && !error && (
        <article className="panel panel-full card">
          <p className="digest-empty">还没有早报。点击上方「立即生成一期」试试。</p>
        </article>
      )}
    </AnimatedCardGrid>
  );
}
