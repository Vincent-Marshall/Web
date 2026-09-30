"use client";

// 门户首页：hero + 每日三区（诗词 / 英文句子 / 画作鉴赏，各带 AI 赏析）+ 身份卡。
// 数据流：GET /api/daily。后端对第三方源有本地兜底、按日期缓存，正常情况不会加载失败。
import { useEffect, useState } from "react";
import Nav from "./Nav.jsx";
import PageHeading from "./PageHeading.jsx";
import AnimatedCardGrid from "./AnimatedCardGrid.jsx";
import { home } from "../data/site.js";

const API = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function HomeView() {
  const [daily, setDaily] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/daily`)
      .then((res) => {
        if (!res.ok) throw new Error(`加载失败：${res.status}`);
        return res.json();
      })
      .then(setDaily)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <AnimatedCardGrid className="dashboard-grid">
      <article className="hero-stage panel-full">
        <Nav />
        <PageHeading title={home.heroTitle} subtitle={home.heroSubtitle} />
      </article>

      {daily && (
        <>
          <article className="panel panel-full card daily-zone">
            <p className="section-kicker">每日诗词</p>
            <p className="daily-poem">{daily.poem.content}</p>
            <p className="daily-meta">
              —— {daily.poem.author}《{daily.poem.title}》
            </p>
            {daily.poem.appreciation && (
              <p className="daily-appreciation">AI 赏析：{daily.poem.appreciation}</p>
            )}
          </article>

          <article className="panel panel-full card daily-zone">
            <p className="section-kicker">每日英文句子</p>
            <p className="daily-quote">“{daily.quote.content}”</p>
            <p className="daily-meta">—— {daily.quote.author}</p>
            {daily.quote.appreciation && (
              <p className="daily-appreciation">AI 赏析：{daily.quote.appreciation}</p>
            )}
          </article>

          <article className="panel panel-full card daily-zone daily-zone-painting">
            {daily.painting.image && (
              <img
                className="daily-painting"
                src={daily.painting.image}
                alt={daily.painting.title}
              />
            )}
            <p className="section-kicker">每日画作鉴赏</p>
            <p className="daily-meta">
              {daily.painting.title} · {daily.painting.artist}（{daily.painting.year}）
            </p>
            {daily.painting.appreciation && (
              <p className="daily-appreciation">AI 赏析：{daily.painting.appreciation}</p>
            )}
          </article>
        </>
      )}

      {!daily && !error && (
        <article className="panel panel-full card">
          <p className="digest-empty">今日内容加载中…</p>
        </article>
      )}
      {error && (
        <article className="panel panel-full card">
          <p className="lab-error">今日内容加载失败：{error}</p>
        </article>
      )}
    </AnimatedCardGrid>
  );
}
