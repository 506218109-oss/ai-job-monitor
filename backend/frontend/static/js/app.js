// AI Job Monitor
(function() {
  'use strict';

  const DAILY_QUOTES = [
    {
      text: '千里之行，始于足下。',
      author: '老子',
      source: '《道德经》',
      url: '',
      note: 'AI 时代的步伐很快，但真正能安顿人的，仍然是今天这一小步。'
    },
    {
      text: '君子不器。',
      author: '孔子',
      source: '《论语·为政》',
      url: '',
      note: '人不必被一个岗位名、一个工具栈或一次面试结果定义。能力会迁移，眼界也会生长。'
    },
    {
      text: '人皆可以为尧舜。',
      author: '孟子',
      source: '《孟子·告子下》',
      url: '',
      note: '成长不是少数人的特权。你可以慢一点，但不必怀疑自己仍有变好的可能。'
    },
    {
      text: '不积跬步，无以至千里。',
      author: '荀子',
      source: '《荀子·劝学》',
      url: '',
      note: '简历、作品集、表达和判断力，都来自可重复的小练习，而不是一夜之间的飞跃。'
    },
    {
      text: '困扰人的不是事物，而是对事物的看法。',
      author: '爱比克泰德',
      source: '《手册》',
      url: '',
      note: '当市场和技术都显得嘈杂时，先把担心拆成事实、选择和下一步动作。'
    },
    {
      text: '你有力量支配自己的心灵，而不是外界事件。',
      author: '马可·奥勒留',
      source: '《沉思录》',
      url: '',
      note: '招聘节奏、行业热词和他人的进度不完全受你控制；可控的是今天怎样准备、怎样复盘。'
    },
    {
      text: '热爱生命吧。',
      author: '亨利·戴维·梭罗',
      source: '《瓦尔登湖》',
      url: '',
      note: '求职很重要，但它不是生活的全部。睡眠、身体、关系和尊严，也需要被认真照看。'
    },
    {
      text: '不能创造的东西，就还没有真正理解。',
      author: 'Richard Feynman',
      source: 'Caltech Magazine 引述其黑板手稿',
      url: 'https://magazine.caltech.edu/post/biology-through-the-eyes-of-a-physicist',
      note: '把知识变成项目、作品和清晰表达，理解才会扎实，信心也会更具体。'
    },
    {
      text: '生活中没有什么只该被害怕，它更该被理解。',
      author: 'Marie Curie',
      source: 'Nobel Prize Annual Review 2024',
      url: 'https://www.nobelprize.org/uploads/2025/04/annual-review-2024.pdf',
      note: 'AI 带来的不确定感可以被学习、观察和练习慢慢照亮，不必一次性战胜它。'
    },
    {
      text: '喜欢你正在做的事，然后把它做到最好。',
      author: 'Katherine Johnson',
      source: 'NASA 人物档案',
      url: 'https://science.nasa.gov/people/katherine-johnson/',
      note: '选择一个值得投入的问题，用日复一日的质量感替代对风口的焦急追逐。'
    },
    {
      text: '保持饥饿，保持愚拙。',
      author: 'Steve Jobs',
      source: 'Stanford Commencement Address, 2005',
      url: 'https://news.stanford.edu/stories/2005/06/youve-got-find-love-jobs-says',
      note: '保留好奇心，也保留重新开始的能力。承认不会，是学习真正开始的地方。'
    },
    {
      text: '别做全知者，做持续学习者。',
      author: 'Satya Nadella',
      source: 'Microsoft growth mindset 分享',
      url: 'https://news.microsoft.com/apac/2019/05/06/learn-include-empower-grow-how-change-transformation-our-new-reality/',
      note: '转向 AI 岗位不是一次性证明自己，而是一条可以被拆解、练习和迭代的学习曲线。'
    },
    {
      text: '今天仍然是第一天。',
      author: 'Jeff Bezos',
      source: 'Amazon shareholder letters',
      url: 'https://www.aboutamazon.com/about-us/shareholder-letters',
      note: '把今天当作新起点，避免被昨天的拒信、停滞或比较固定住。'
    },
    {
      text: '认识你自己。',
      author: '苏格拉底',
      source: '古希腊箴言',
      url: '',
      note: '技术会持续更新，但你的经验、审美、判断、同理心和行动方式，是求职叙事里的根。'
    },
    {
      text: '我们必须耕种自己的园地。',
      author: '伏尔泰',
      source: '《老实人》',
      url: '',
      note: '行业很大，消息很多。先照看好自己的技能花园：一个项目、一段复盘、一次真诚沟通。'
    },
    {
      text: '山重水复疑无路，柳暗花明又一村。',
      author: '陆游',
      source: '《游山西村》',
      url: '',
      note: '卡住的时候，不代表路已经结束。多一次调整方向，可能就会看到新的入口。'
    }
  ];

  function getBeijingDateKey(date) {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(date);
  }

  function dateKeyToDayIndex(key) {
    const parts = key.split('-').map(Number);
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return 0;
    return Math.floor(Date.UTC(parts[0], parts[1] - 1, parts[2]) / 86400000);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function sourceHtml(quote, className) {
    const label = `${quote.author} · ${quote.source}`;
    if (!quote.url) {
      return `<span class="${className}">${escapeHtml(label)}</span>`;
    }
    return `<a class="${className}" href="${escapeHtml(quote.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
  }

  function getDailyQuote() {
    const dateKey = getBeijingDateKey(new Date());
    const index = dateKeyToDayIndex(dateKey) % DAILY_QUOTES.length;
    return { quote: DAILY_QUOTES[index], dateKey };
  }

  function formatDisplayDate(dateKey) {
    const parts = dateKey.split('-');
    if (parts.length !== 3) return dateKey;
    return `${parts[0]}年${Number(parts[1])}月${Number(parts[2])}日`;
  }

  function renderSidebarQuote(quote) {
    const target = document.getElementById('sidebar-quote');
    if (!target) return;
    const dateKey = getBeijingDateKey(new Date());

    target.innerHTML = `
      <div class="sidebar-quote-label">今日哲思</div>
      <p>${escapeHtml(quote.text)}</p>
      ${sourceHtml(quote, 'sidebar-quote-source')}
    `;
    target.setAttribute('role', 'button');
    target.setAttribute('tabindex', '0');
    target.setAttribute('aria-label', '打开每日哲思弹窗');
    target.onclick = (event) => {
      if (event.target.closest('a')) return;
      renderDailyQuoteModal(quote, dateKey, { forceOpen: true });
    };
    target.onkeydown = (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      renderDailyQuoteModal(quote, dateKey, { forceOpen: true });
    };
  }

  function dismissQuoteModal(dateKey, overlay) {
    try {
      window.localStorage.setItem('ai-job-radar-quote-dismissed', dateKey);
    } catch (error) {
      // Ignore storage failures in private browsing or locked-down browsers.
    }
    overlay.remove();
  }

  function renderDailyQuoteModal(quote, dateKey, options = {}) {
    const params = new URLSearchParams(window.location.search);
    const forceOpen = Boolean(options.forceOpen) || params.has('quote');

    try {
      const dismissedDate = window.localStorage.getItem('ai-job-radar-quote-dismissed');
      if (!forceOpen && dismissedDate === dateKey) return;
    } catch (error) {
      // If localStorage is unavailable, show the card once per page load.
    }

    document.querySelectorAll('.daily-quote-overlay').forEach((node) => node.remove());
    const overlay = document.createElement('div');
    overlay.className = 'daily-quote-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'daily-quote-title');
    overlay.innerHTML = `
      <section class="daily-quote-card">
        <button class="daily-quote-close" type="button" aria-label="关闭每日哲思"><span aria-hidden="true">&times;</span></button>
        <div class="daily-quote-topline" id="daily-quote-title">
          <span class="daily-quote-pill">今日哲思</span>
          <span class="daily-quote-date">${escapeHtml(formatDisplayDate(dateKey))}</span>
        </div>
        <div class="daily-quote-content">
          <div class="daily-quote-mark" aria-hidden="true">“</div>
          <blockquote>${escapeHtml(quote.text)}</blockquote>
        </div>
        <p class="daily-quote-note">${escapeHtml(quote.note)}</p>
        <div class="daily-quote-footer">
          <div class="daily-quote-meta">
            <span>作者 / 出处</span>
            ${sourceHtml(quote, 'daily-quote-source')}
          </div>
          <button class="daily-quote-action" type="button">进入今日雷达</button>
        </div>
      </section>
    `;

    overlay.addEventListener('click', (event) => {
      if (
        event.target === overlay ||
        event.target.closest('.daily-quote-close') ||
        event.target.closest('.daily-quote-action')
      ) {
        dismissQuoteModal(dateKey, overlay);
      }
    });

    document.addEventListener('keydown', function onEscape(event) {
      if (event.key !== 'Escape' || !document.body.contains(overlay)) return;
      dismissQuoteModal(dateKey, overlay);
      document.removeEventListener('keydown', onEscape);
    });

    document.body.appendChild(overlay);
  }

  function initDailyQuote() {
    const { quote, dateKey } = getDailyQuote();
    renderSidebarQuote(quote);
    renderDailyQuoteModal(quote, dateKey);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDailyQuote);
  } else {
    initDailyQuote();
  }
})();
