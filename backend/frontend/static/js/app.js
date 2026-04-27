// AI Job Monitor
(function() {
  'use strict';

  const DAILY_QUOTES = [
    {
      text: '保持饥饿，保持愚拙。',
      author: 'Steve Jobs',
      source: 'Stanford Commencement Address, 2005',
      url: 'https://news.stanford.edu/stories/2005/06/youve-got-find-love-jobs-says',
      note: '保留好奇心，也保留重新开始的能力。'
    },
    {
      text: '别做全知者，做持续学习者。',
      author: 'Satya Nadella',
      source: 'Microsoft growth mindset 分享',
      url: 'https://news.microsoft.com/apac/2019/05/06/learn-include-empower-grow-how-change-transformation-our-new-reality/',
      note: '求职和转岗本质上都是学习曲线，而不是一次性证明。'
    },
    {
      text: '不能创造的东西，就还没有真正理解。',
      author: 'Richard Feynman',
      source: 'Caltech Magazine 引述其黑板手稿',
      url: 'https://magazine.caltech.edu/post/biology-through-the-eyes-of-a-physicist',
      note: '把知识变成项目、作品和表达，理解才会扎实。'
    },
    {
      text: '喜欢你正在做的事，然后把它做到最好。',
      author: 'Katherine Johnson',
      source: 'NASA 人物档案',
      url: 'https://science.nasa.gov/people/katherine-johnson/',
      note: '选择值得投入的方向，再用日复一日的质量感建立信心。'
    },
    {
      text: '生活中没有什么只该被害怕，它更该被理解。',
      author: 'Marie Curie',
      source: 'Nobel Prize Annual Review 2024',
      url: 'https://www.nobelprize.org/uploads/2025/04/annual-review-2024.pdf',
      note: '焦虑可以先拆成事实、问题和下一步动作。'
    },
    {
      text: '今天仍然是第一天。',
      author: 'Jeff Bezos',
      source: 'Amazon shareholder letters',
      url: 'https://www.aboutamazon.com/about-us/shareholder-letters',
      note: '把今天当作新起点，避免被昨天的结果固定住。'
    },
    {
      text: '多创造一些，少消耗一些。',
      author: 'Jeff Bezos',
      source: '2020 Letter to Shareholders',
      url: 'https://www.aboutamazon.com/news/company-news/2020-letter-to-shareholders/',
      note: '作品、复盘、面试案例和真实贡献，都会比空想更能推进生活。'
    },
    {
      text: '你必须找到自己真正热爱的东西。',
      author: 'Steve Jobs',
      source: 'Stanford Commencement Address, 2005',
      url: 'https://news.stanford.edu/stories/2005/06/youve-got-find-love-jobs-says',
      note: '热爱不是口号，它通常藏在你愿意长期打磨的具体问题里。'
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

  function hashDateKey(key) {
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
      hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
    }
    return hash;
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
    const index = hashDateKey(dateKey) % DAILY_QUOTES.length;
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

    target.innerHTML = `
      <div class="sidebar-quote-label">今日哲思</div>
      <p>${escapeHtml(quote.text)}</p>
      ${sourceHtml(quote, 'sidebar-quote-source')}
    `;
  }

  function dismissQuoteModal(dateKey, overlay) {
    try {
      window.localStorage.setItem('ai-job-radar-quote-dismissed', dateKey);
    } catch (error) {
      // Ignore storage failures in private browsing or locked-down browsers.
    }
    overlay.remove();
  }

  function renderDailyQuoteModal(quote, dateKey) {
    const params = new URLSearchParams(window.location.search);
    const forceOpen = params.has('quote');

    try {
      const dismissedDate = window.localStorage.getItem('ai-job-radar-quote-dismissed');
      if (!forceOpen && dismissedDate === dateKey) return;
    } catch (error) {
      // If localStorage is unavailable, show the card once per page load.
    }

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
