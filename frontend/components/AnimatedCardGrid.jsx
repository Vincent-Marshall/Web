// 卡片网格容器。
// 入场动画已改为纯 CSS（css/cards.css 的 @keyframes card-in），
// 本组件不再负责动画——JS 动画失败曾导致卡片永久 invisible 的生产事故。
// 保留组件名以免各页面引用改动，它现在只是一个语义化容器。
export default function AnimatedCardGrid({ className, children }) {
  return <section className={className}>{children}</section>;
}
