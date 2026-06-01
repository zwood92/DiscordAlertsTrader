document.addEventListener("DOMContentLoaded", () => {
    // Nav Tab Switcher
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanels = document.querySelectorAll(".tab-panel");

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = item.getAttribute("data-tab");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            tabPanels.forEach(panel => panel.classList.remove("active"));
            
            item.classList.add("active");
            document.getElementById(tabId).classList.add("active");
            
            // Fetch tab data on load
            loadTabData(tabId);
        });
    });

    // WebSocket Management
    let ws;
    const connectWS = () => {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        
        ws.onopen = () => {
            console.log("WebSocket connected.");
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "log") {
                appendLog(data.data);
            }
        };
        
        ws.onclose = () => {
            console.log("WebSocket closed. Reconnecting in 3s...");
            setTimeout(connectWS, 3000);
        };
    };
    connectWS();

    const subsLog = document.getElementById("console-subs-log");
    const allLog = document.getElementById("console-all-log");
    
    // Subscribed filter
    const subsFilter = document.getElementById("console-subscribed-filter");

    const appendLog = (msg) => {
        const div = document.createElement("div");
        div.textContent = msg.text;
        
        // Add color class
        if (msg.color) {
            div.classList.add(`log-${msg.color}`);
        } else {
            div.classList.add("log-white");
        }
        
        // Broadcast to "All Discord Logs"
        const divAll = div.cloneNode(true);
        allLog.appendChild(divAll);
        allLog.scrollTop = allLog.scrollHeight;
        
        // Filter subscribed
        const filterVal = subsFilter.value;
        // Subscribed message identifier flag is "blue" or contains specific sub keywords in Qt original code
        const isSubscribed = msg.color === "blue" || msg.bg === "blue" || filterVal === "All Subscribed";
        
        if (isSubscribed) {
            if (filterVal === "All Subscribed" || msg.text.toLowerCase().includes(filterVal.toLowerCase())) {
                subsLog.appendChild(div);
                subsLog.scrollTop = subsLog.scrollHeight;
            }
        }
    };

    // Load dynamic dropdown authors list on initial load
    let subscribedAuthorsList = [];
    const loadSubscribedAuthors = async () => {
        try {
            const res = await fetch("/api/config");
            const data = await res.json();
            if (data.subscribed_analysts) {
                subscribedAuthorsList = data.subscribed_analysts.map(a => a.split("#")[0].trim());
                
                // Populate Subscribed console filter
                subsFilter.innerHTML = '<option value="All Subscribed">All Subscribed</option>';
                subscribedAuthorsList.forEach(author => {
                    const opt = document.createElement("option");
                    opt.value = author;
                    opt.textContent = author;
                    subsFilter.appendChild(opt);
                });
                
                // Populate filtering lists in tabs
                ["port-filt-author", "track-filt-author", "stat-filt-author"].forEach(selectId => {
                    const select = document.getElementById(selectId);
                    if (select) {
                        select.innerHTML = '<option value="All" selected>All</option>';
                        subscribedAuthorsList.forEach(author => {
                            const opt = document.createElement("option");
                            opt.value = author;
                            opt.textContent = author;
                            select.appendChild(opt);
                        });
                    }
                });
            }
        } catch (e) {
            console.error("Failed to load subscribed authors:", e);
        }
    };
    loadSubscribedAuthors();

    // Trigger tab data on change of timeframe or filter
    document.getElementById("dash-timeframe").addEventListener("change", () => loadTabData("dashboard"));
    
    // Setup listeners on table filters
    const setupFilterListeners = (prefix, tabName) => {
        const filters = document.querySelectorAll(`.${prefix}-excl, #${prefix}-filt-date-frm, #${prefix}-filt-date-to`);
        filters.forEach(f => {
            f.addEventListener("change", () => loadTabData(tabName));
        });
        
        const textInputs = document.querySelectorAll(`#${prefix}-filt-sym, #${prefix}-filt-chn, #${prefix}-dte-min, #${prefix}-dte-max`);
        textInputs.forEach(input => {
            input.addEventListener("keyup", (e) => {
                if (e.key === "Enter") loadTabData(tabName);
            });
        });
    };
    setupFilterListeners("port", "portfolio");
    setupFilterListeners("track", "analysts-portfolio");
    setupFilterListeners("stats", "analysts-stats");

    // Setup manual Refresh Buttons
    document.getElementById("btn-refresh-port").addEventListener("click", () => loadTabData("portfolio"));
    document.getElementById("btn-refresh-track").addEventListener("click", () => loadTabData("analysts-portfolio"));
    document.getElementById("btn-refresh-stats").addEventListener("click", () => loadTabData("analysts-stats"));
    document.getElementById("btn-refresh-exits").addEventListener("click", () => loadTabData("strategy-exits"));
    document.getElementById("btn-refresh-history").addEventListener("click", () => loadTabData("msg-history"));
    document.getElementById("btn-refresh-account").addEventListener("click", () => loadTabData("account"));

    // Quick Trade Submissions
    document.getElementById("qt-btn-trigger").addEventListener("click", async () => {
        const msg = document.getElementById("qt-message").value.trim();
        const portfolio = document.getElementById("qt-portfolio").value;
        if (!msg) return alert("Please select a row or enter manual alert content.");
        
        try {
            const res = await fetch("/api/quick_trade/trigger", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: msg, portfolio: portfolio })
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById("qt-message").value = "";
                alert("Alert successfully triggered.");
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (e) {
            alert(`Network error: ${e.message}`);
        }
    });

    // Quick Trade Action Buttons (BTO, STC, STO, BTC, exitupdate, quotes, plot)
    document.querySelectorAll(".btn-action").forEach(btn => {
        btn.addEventListener("click", async () => {
            const action = btn.getAttribute("data-action");
            const msg = document.getElementById("qt-message").value.trim();
            const qty = document.getElementById("qt-qty").value;
            
            if (!msg) return alert("Select a row or enter default alert message first.");
            
            try {
                const res = await fetch("/api/quick_trade/action", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action: action, message: msg, quantity: qty })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById("qt-message").value = data.message;
                    document.getElementById("qt-current-trade").textContent = data.message;
                } else {
                    alert(`Trade parsing error: ${data.error}`);
                }
            } catch (e) {
                alert(`Action error: ${e.message}`);
            }
        });
    });

    // Quick Trade Manual Scale buttons (25, 50, 75, 100)
    document.querySelectorAll(".btn-scale").forEach(btn => {
        btn.addEventListener("click", async () => {
            const scale = btn.getAttribute("data-scale");
            const msg = document.getElementById("qt-message").value.trim();
            
            if (!msg) return alert("Please select a valid alert row first.");
            
            try {
                const res = await fetch("/api/quick_trade/action", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action: `scale_${scale}`, message: msg })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById("qt-message").value = data.message;
                    document.getElementById("qt-current-trade").textContent = data.message;
                }
            } catch (e) {
                console.error(e);
            }
        });
    });

    // Reconcile Broker Portfolio
    document.getElementById("qt-btn-reconcile").addEventListener("click", async () => {
        try {
            const res = await fetch("/api/quick_trade/reconcile", { method: "POST" });
            const data = await res.json();
            if (data.success) {
                alert(`Reconciliation Results:\n\n${data.report}`);
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (e) {
            alert(`Reconcile call error: ${e.message}`);
        }
    });

    // Central Tab Data Fetcher dispatcher
    const loadTabData = (tabId) => {
        switch (tabId) {
            case "dashboard":
                fetchDashboard();
                break;
            case "portfolio":
                fetchPortfolio();
                break;
            case "analysts-portfolio":
                fetchTracker();
                break;
            case "analysts-stats":
                fetchStats();
                break;
            case "strategy-exits":
                fetchStrategyExits();
                break;
            case "msg-history":
                fetchMsgHistory();
                break;
            case "account":
                fetchAccount();
                break;
            case "config":
                fetchConfig();
                break;
        }
    };

    // 1. Fetch Dashboard
    const fetchDashboard = async () => {
        const timeframe = document.getElementById("dash-timeframe").value;
        try {
            const res = await fetch("/api/dashboard", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ timeframe: timeframe })
            });
            const data = await res.json();
            
            // Fill metrics card values
            const pnlCard = document.getElementById("dash-total-pnl");
            pnlCard.textContent = data.total_pnl;
            pnlCard.className = "value " + (data.total_pnl.startsWith("$-") ? "negative" : "positive");
            
            document.getElementById("dash-win-rate").textContent = data.win_rate;
            document.getElementById("dash-total-trades").textContent = data.total_trades;
            
            const botCard = document.getElementById("dash-bot-status");
            botCard.textContent = data.bot_status;
            botCard.className = "value " + (data.bot_status === "ACTIVE" ? "active" : "stopped");
            
            // Fill Sentiment Radar
            const sentimentCard = document.getElementById("dash-sentiment");
            sentimentCard.textContent = data.sentiment;
            sentimentCard.className = data.sentiment.toLowerCase();
            document.getElementById("dash-rationale").textContent = data.rationale;
            
            // Load chart curve
            const chartImg = document.getElementById("dash-equity-chart");
            if (data.equity_chart_url) {
                chartImg.src = data.equity_chart_url;
            } else {
                chartImg.src = "";
                chartImg.alt = "Equity Curve (Add closed trades to build graphics)";
            }
            
            // Fill Top performers table
            const tbody = document.querySelector("#dash-top-analysts-table tbody");
            tbody.innerHTML = "";
            if (data.recent_performance && data.recent_performance.length > 0) {
                data.recent_performance.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td><strong>${row[0]}</strong></td><td>${row[1]}</td><td class="pnl-positive font-bold">${row[2]}</td>`;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = "<tr><td colspan='3' class='text-center'>No active analyst alerts recorded.</td></tr>";
            }
            
        } catch (e) {
            console.error("Dashboard metrics loader error:", e);
        }
    };

    // 2. Fetch User Portfolio Grid
    const fetchPortfolio = async () => {
        const body = {
            Closed: document.getElementById("port-excl-Closed").checked,
            Open: document.getElementById("port-excl-Open").checked,
            Canceled: document.getElementById("port-excl-Canceled").checked,
            Rejected: document.getElementById("port-excl-Rejected").checked,
            NegPnL: document.getElementById("port-excl-NegPnL").checked,
            PosPnL: document.getElementById("port-excl-PosPnL").checked,
            "live PnL": document.getElementById("port-excl-live-PnL").checked,
            stocks: document.getElementById("port-excl-stocks").checked,
            options: document.getElementById("port-excl-options").checked,
            bto: document.getElementById("port-excl-bto").checked,
            sto: document.getElementById("port-excl-sto").checked,
            
            // filter details
            filt_author: getSelectValues(document.getElementById("port-filt-author")),
            filt_date_frm: document.getElementById("port-filt-date-frm").value,
            filt_date_to: document.getElementById("port-filt-date-to").value,
            filt_sym: document.getElementById("port-filt-sym").value.trim(),
            filt_chn: document.getElementById("port-filt-chn").value.trim()
        };
        
        try {
            const res = await fetch("/api/portfolio", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            renderTable("port-table", data.headers, data.data, "port");
        } catch (e) {
            console.error(e);
        }
    };

    // 3. Fetch Analyst Alerts Grid
    const fetchTracker = async () => {
        const body = {
            Closed: document.getElementById("track-excl-Closed").checked,
            Open: document.getElementById("track-excl-Open").checked,
            NegPnL: document.getElementById("track-excl-NegPnL").checked,
            PosPnL: document.getElementById("track-excl-PosPnL").checked,
            "live PnL": document.getElementById("track-excl-live-PnL").checked,
            stocks: document.getElementById("track-excl-stocks").checked,
            options: document.getElementById("track-excl-options").checked,
            bto: document.getElementById("track-excl-bto").checked,
            sto: document.getElementById("track-excl-sto").checked,
            
            // filters
            filt_author: getSelectValues(document.getElementById("track-filt-author")),
            filt_date_frm: document.getElementById("track-filt-date-frm").value,
            filt_date_to: document.getElementById("track-filt-date-to").value,
            filt_sym: document.getElementById("track-filt-sym").value.trim(),
            filt_chn: document.getElementById("track-filt-chn").value.trim(),
            dte_min: document.getElementById("track-dte-min").value,
            dte_max: document.getElementById("track-dte-max").value
        };
        
        try {
            const res = await fetch("/api/tracker", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            renderTable("track-table", data.headers, data.data, "track");
        } catch (e) {
            console.error(e);
        }
    };

    // 4. Fetch Analyst Performance Stats
    const fetchStats = async () => {
        const body = {
            NegPnL: document.getElementById("stats-excl-NegPnL").checked,
            PosPnL: document.getElementById("stats-excl-PosPnL").checked,
            stocks: document.getElementById("stats-excl-stocks").checked,
            options: document.getElementById("stats-excl-options").checked,
            bto: document.getElementById("stats-excl-bto").checked,
            sto: document.getElementById("stats-excl-sto").checked,
            
            // filters
            filt_author: getSelectValues(document.getElementById("stat-filt-author")),
            filt_date_frm: document.getElementById("stat-filt-date-frm").value.trim(),
            filt_date_to: document.getElementById("stat-filt-date-to").value.trim(),
            filt_sym: document.getElementById("stat-filt-sym").value.trim(),
            max_trade_val: document.getElementById("stat-max-trade-val").value,
            max_qty: document.getElementById("stat-max-qty").value,
            dte_min: document.getElementById("stat-dte-min").value,
            dte_max: document.getElementById("stat-dte-max").value
        };
        
        try {
            const res = await fetch("/api/stats", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            renderTable("stats-table", data.headers, data.data, "stats");
        } catch (e) {
            console.error(e);
        }
    };

    // 5. Fetch Backtested Exits Comparison
    const fetchStrategyExits = async () => {
        try {
            const res = await fetch("/api/strategy_exits");
            const data = await res.json();
            renderTable("exits-comp-table", data.comparison.headers, data.comparison.data);
            renderTable("exits-opt-table", data.optimizations.headers, data.optimizations.data);
        } catch (e) {
            console.error(e);
        }
    };

    // 6. Fetch Msg History channels
    const fetchMsgHistory = async () => {
        const channelSelect = document.getElementById("hist-channel");
        
        const body = {
            channel: channelSelect.value || "",
            filt_author: document.getElementById("hist-author").value.trim(),
            filt_date_frm: document.getElementById("hist-date-frm").value.trim(),
            filt_date_to: document.getElementById("hist-date-to").value.trim(),
            filt_cont: document.getElementById("hist-content").value.trim()
        };
        
        try {
            const res = await fetch("/api/msg_history", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            
            // Build channel dropdown list if empty
            if (channelSelect.options.length <= 1 && data.channels) {
                channelSelect.innerHTML = "";
                data.channels.forEach(ch => {
                    const opt = document.createElement("option");
                    opt.value = ch;
                    opt.textContent = ch;
                    channelSelect.appendChild(opt);
                });
                
                // Select first channel and re-fetch if channel was empty
                if (!body.channel && data.channels.length > 0) {
                    channelSelect.value = data.channels[0];
                    body.channel = data.channels[0];
                    // Refetch again with chosen channel
                    const secondRes = await fetch("/api/msg_history", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body)
                    });
                    const secondData = await secondRes.json();
                    renderTable("hist-table", secondData.headers, secondData.data);
                    return;
                }
            }
            
            renderTable("hist-table", data.headers, data.data);
        } catch (e) {
            console.error(e);
        }
    };
    // Re-fetch message history on drop change
    document.getElementById("hist-channel").addEventListener("change", () => loadTabData("msg-history"));
    
    // Bind enter key on history filter fields
    ["hist-author", "hist-date-frm", "hist-date-to", "hist-content"].forEach(id => {
        document.getElementById(id).addEventListener("keyup", (e) => {
            if (e.key === "Enter") loadTabData("msg-history");
        });
    });

    // 7. Fetch Real Brokerage Account details
    const fetchAccount = async () => {
        const container = document.getElementById("account-status-block");
        try {
            const res = await fetch("/api/account");
            const data = await res.json();
            
            if (!data.connected) {
                container.innerHTML = `
                    <div class="panel text-center">
                        <h3 style="color: var(--accent-red)">Broker Offline</h3>
                        <p>${data.error || "No brokerage API credentials provided or offline inside config.ini"}</p>
                    </div>
                `;
                renderTable("acc-positions-table", ["Positions"], [["No positions available"]]);
                renderTable("acc-orders-table", ["Orders"], [["No working orders available"]]);
                return;
            }
            
            // Build dynamic balances block
            container.innerHTML = `
                <div class="broker-status-card">
                    <div class="broker-status-item">
                        <span>Connected Broker</span>
                        <strong style="color: var(--accent-blue)">${data.broker.toUpperCase()}</strong>
                    </div>
                    <div class="broker-status-item">
                        <span>Liquidation Value</span>
                        <strong>$${data.info.balance.toFixed(2)}</strong>
                    </div>
                    <div class="broker-status-item">
                        <span>Available Cash</span>
                        <strong>$${data.info.cash.toFixed(2)}</strong>
                    </div>
                    <div class="broker-status-item">
                        <span>Buying Power</span>
                        <strong>$${data.info.funds.toFixed(2)}</strong>
                    </div>
                </div>
            `;
            
            renderTable("acc-positions-table", data.positions.headers, data.positions.data);
            renderTable("acc-orders-table", data.orders.headers, data.orders.data);
        } catch (e) {
            container.innerHTML = `
                <div class="panel text-center">
                    <h3 style="color: var(--accent-red)">Broker Retrieval Error</h3>
                    <p>${e.message}</p>
                </div>
            `;
        }
    };

    // 8. Fetch Session Config settings
    const fetchConfig = async () => {
        const form = document.getElementById("config-form");
        try {
            const res = await fetch("/api/config");
            const data = await res.json();
            
            form.innerHTML = "";
            const sections = data.config;
            
            // Category sections inside columns
            const col1 = document.createElement("div");
            col1.className = "column-flex";
            const col2 = document.createElement("div");
            col2.className = "column-flex";
            
            // Section 1: General & Subscriptions
            const cardGen = document.createElement("div");
            cardGen.className = "config-section-card";
            cardGen.innerHTML = `
                <h3 class="green">General Settings</h3>
                <div class="config-field">
                    <label>Sampling Rate Quotes (seconds):</label>
                    <input type="text" name="cfg_general.sampling_rate_quotes" value="${sections.general?.sampling_rate_quotes || ''}" />
                </div>
                <div class="config-field">
                    <label>Off Market hours eastern (e.g. 16,9):</label>
                    <input type="text" name="cfg_general.off_hours" value="${sections.general?.off_hours || ''}" />
                </div>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_general.do_BTO_trades" ${sections.general?.do_bto_trades === 'True' || sections.general?.do_bto_trades === 'true' ? 'checked' : ''} />
                    <span>Do BTO Long Trades</span>
                </label>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_general.do_STC_trades" ${sections.general?.do_stc_trades === 'True' || sections.general?.do_stc_trades === 'true' ? 'checked' : ''} />
                    <span>Do STC Close Trades</span>
                </label>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_general.live_quotes_options_only" ${sections.general?.live_quotes_options_only === 'True' || sections.general?.live_quotes_options_only === 'true' ? 'checked' : ''} />
                    <span>Live quotes options only</span>
                </label>
            `;
            col1.appendChild(cardGen);
            
            // Section 2: Long Position Risk Capital sizing
            const cardLong = document.createElement("div");
            cardLong.className = "config-section-card";
            cardLong.innerHTML = `
                <h3 class="green">Long Position Config</h3>
                <div class="config-field">
                    <label>Authors Subscribed:</label>
                    <input type="text" name="cfg_discord.authors_subscribed" value="${sections.discord?.authors_subscribed || ''}" />
                </div>
                <div class="config-field">
                    <label>Trade Capital limit per trade ($):</label>
                    <input type="text" name="cfg_order_configs.trade_capital" value="${sections.order_configs?.trade_capital || ''}" />
                </div>
                <div class="config-field">
                    <label>Max Capital limit ($):</label>
                    <input type="text" name="cfg_order_configs.max_trade_capital" value="${sections.order_configs?.max_trade_capital || ''}" />
                </div>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_risk_management.move_to_breakeven_pt1" ${sections.risk_management?.move_to_breakeven_pt1 === 'True' || sections.risk_management?.move_to_breakeven_pt1 === 'true' ? 'checked' : ''} />
                    <span>Move Stop to Break-Even after PT1 hit</span>
                </label>
            `;
            col1.appendChild(cardLong);
            
            // Section 3: Shorting Settings
            const cardShort = document.createElement("div");
            cardShort.className = "config-section-card";
            cardShort.innerHTML = `
                <h3 class="red">Short Position Config</h3>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_shorting.DO_STO_TRADES" ${sections.shorting?.do_sto_trades === 'True' || sections.shorting?.do_sto_trades === 'true' ? 'checked' : ''} />
                    <span>Do STO Short Trades</span>
                </label>
                <label class="config-field-checkbox">
                    <input type="checkbox" name="cfg_shorting.DO_BTC_TRADES" ${sections.shorting?.do_btc_trades === 'True' || sections.shorting?.do_btc_trades === 'true' ? 'checked' : ''} />
                    <span>Do BTC Short Closes</span>
                </label>
                <div class="config-field">
                    <label>Margin Capital limit ($):</label>
                    <input type="text" name="cfg_shorting.margin_capital" value="${sections.shorting?.margin_capital || ''}" />
                </div>
                <div class="config-field">
                    <label>BTC PT % limit:</label>
                    <input type="text" name="cfg_shorting.BTC_PT" value="${sections.shorting?.btc_pt || ''}" />
                </div>
                <div class="config-field">
                    <label>BTC SL % limit:</label>
                    <input type="text" name="cfg_shorting.BTC_SL" value="${sections.shorting?.btc_sl || ''}" />
                </div>
            `;
            col2.appendChild(cardShort);
            
            // Section 4: Default Exits configuration values
            const cardExits = document.createElement("div");
            cardExits.className = "config-section-card";
            cardExits.innerHTML = `
                <h3 class="green">Default Exits (Virtual Plan)</h3>
                <div class="config-field">
                    <label>PT1 % (e.g. 30% or 30%TS5%):</label>
                    <input type="text" name="cfg_exits_PT1" value="${sections.default_exits?.PT1 || ''}" />
                </div>
                <div class="config-field">
                    <label>PT2 %:</label>
                    <input type="text" name="cfg_exits_PT2" value="${sections.default_exits?.PT2 || ''}" />
                </div>
                <div class="config-field">
                    <label>PT3 %:</label>
                    <input type="text" name="cfg_exits_PT3" value="${sections.default_exits?.PT3 || ''}" />
                </div>
                <div class="config-field">
                    <label>Stop Loss (SL) % (e.g. 15%):</label>
                    <input type="text" name="cfg_exits_SL" value="${sections.default_exits?.SL || ''}" />
                </div>
            `;
            col2.appendChild(cardExits);
            
            // Section 5: Exit Strategy Select Choices
            const cardStrat = document.createElement("div");
            cardStrat.className = "config-section-card";
            const activeStrat = sections.order_configs?.active_exit_strategy || "Original STC";
            cardStrat.innerHTML = `
                <h3 class="green">Exit Strategy Controls</h3>
                <div class="config-field">
                    <label>Active Exit Strategy:</label>
                    <select name="cfg_order_configs.active_exit_strategy">
                        <option value="Original STC" ${activeStrat === "Original STC" ? 'selected' : ''}>Original STC</option>
                        <option value="Manual Default Exits" ${activeStrat === "Manual Default Exits" ? 'selected' : ''}>Manual Default Exits</option>
                        <option value="Strategy 1 (Trim Detector)" ${activeStrat === "Strategy 1 (Trim Detector)" ? 'selected' : ''}>Strategy 1 (Trim Detector)</option>
                        <option value="Strategy 2 (MAE Stop)" ${activeStrat === "Strategy 2 (MAE Stop)" ? 'selected' : ''}>Strategy 2 (MAE Stop)</option>
                        <option value="Strategy 3 (Fixed Trailing Stop)" ${activeStrat === "Strategy 3 (Fixed Trailing Stop)" ? 'selected' : ''}>Strategy 3 (Fixed Trailing Stop)</option>
                        <option value="Strategy 4 (ATR TS)" ${activeStrat === "Strategy 4 (ATR TS)" ? 'selected' : ''}>Strategy 4 (ATR TS)</option>
                    </select>
                </div>
                <div class="config-field">
                    <label>Strat 2 MAE Multiplier:</label>
                    <input type="text" name="cfg_order_configs.mae_multiplier" value="${sections.order_configs?.mae_multiplier || ''}" />
                </div>
                <div class="config-field">
                    <label>Strat 3 Trailing Stop %:</label>
                    <input type="text" name="cfg_order_configs.fixed_ts_pct" value="${sections.order_configs?.fixed_ts_pct || ''}" />
                </div>
                <div class="config-field">
                    <label>Strat 4 ATR Multiplier:</label>
                    <input type="text" name="cfg_order_configs.atr_multiplier" value="${sections.order_configs?.atr_multiplier || ''}" />
                </div>
            `;
            col2.appendChild(cardStrat);
            
            form.appendChild(col1);
            form.appendChild(col2);
            
            // Add central Save Button
            const saveBtnRow = document.createElement("div");
            saveBtnRow.className = "config-save-row";
            saveBtnRow.innerHTML = `
                <button type="submit" class="btn btn-primary">SAVE CONFIGURATION CHANGES</button>
            `;
            form.appendChild(saveBtnRow);
            
            // Listen for form submissions
            form.addEventListener("submit", async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const bodyObj = {};
                formData.forEach((val, key) => {
                    bodyObj[key] = val;
                });
                
                // Set explicit boolean flags for unchecked checkboxes
                form.querySelectorAll('input[type="checkbox"]').forEach(box => {
                    bodyObj[box.name] = box.checked;
                });
                
                try {
                    const saveRes = await fetch("/api/config/save", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(bodyObj)
                    });
                    const saveResult = await saveRes.json();
                    if (saveResult.success) {
                        alert("Configurations written successfully back to config.ini");
                        loadSubscribedAuthors(); // Reload authors just in case they were modified
                        loadTabData("config");
                    } else {
                        alert(`Error saving configs: ${saveResult.error}`);
                    }
                } catch (e) {
                    alert(`Network error saving configs: ${e.message}`);
                }
            });
            
        } catch (e) {
            form.innerHTML = `<p style="color: var(--accent-red)">Configuration Load Error: ${e.message}</p>`;
        }
    };

    // Table renderer helper
    const renderTable = (tableId, headers, data, typePrefix = "") => {
        const table = document.getElementById(tableId);
        if (!table) return;
        
        table.innerHTML = "";
        
        // Build Thead
        const thead = document.createElement("thead");
        const headerTr = document.createElement("tr");
        
        // Render Row Number header if applicable
        if (typePrefix) {
            const thNum = document.createElement("th");
            thNum.textContent = "#";
            headerTr.appendChild(thNum);
        }
        
        headers.forEach(h => {
            const th = document.createElement("th");
            th.textContent = h;
            headerTr.appendChild(th);
        });
        thead.appendChild(headerTr);
        table.appendChild(thead);
        
        // Build Tbody
        const tbody = document.createElement("tbody");
        if (!data || data.length === 0 || (data.length === 1 && data[0].length === 0)) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = headers.length + (typePrefix ? 1 : 0);
            td.textContent = "No matching records found.";
            td.className = "text-center";
            tr.appendChild(td);
            tbody.appendChild(tr);
            table.appendChild(tbody);
            return;
        }
        
        data.forEach((row, rowIdx) => {
            const tr = document.createElement("tr");
            tr.setAttribute("data-row-idx", rowIdx);
            
            // Add row index selector
            if (typePrefix) {
                const tdNum = document.createElement("td");
                tdNum.innerHTML = `<strong>${rowIdx}</strong>`;
                tdNum.style.color = "var(--text-muted)";
                tr.appendChild(tdNum);
            }
            
            row.forEach((cell, cellIdx) => {
                const td = document.createElement("td");
                td.textContent = cell;
                
                // Colorize PnL cells
                const header = headers[cellIdx];
                if (header && (header.includes("PnL") || header.includes("Win Rate") || header.includes("Win act"))) {
                    const text = String(cell).trim();
                    if (text && !text.startsWith("0.00") && text !== "") {
                        if (text.startsWith("-") || text.includes("$-")) {
                            td.className = "pnl-cell pnl-negative";
                        } else if (!text.startsWith("nan")) {
                            td.className = "pnl-cell pnl-positive";
                        }
                    }
                }
                tr.appendChild(td);
            });
            
            // Catch clicks on table rows to pre-fill trades console
            if (typePrefix === "port" || typePrefix === "track") {
                tr.addEventListener("click", () => {
                    // Deselect previous
                    tbody.querySelectorAll("tr").forEach(r => r.classList.remove("row-selected"));
                    tr.classList.add("row-selected");
                    
                    prefillQuickTrade(row, headers, typePrefix);
                });
            }
            
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
    };

    // Row selection trade prefill logic
    const prefillQuickTrade = (row, headers, typePrefix) => {
        try {
            // Find key indices
            const traderIdx = headers.indexOf("Trader");
            const symbolIdx = headers.indexOf("Symbol");
            
            // Use filledQty for user port, Qty for tracker
            const qtyIdx = typePrefix === "port" ? headers.indexOf("filledQty") : headers.indexOf("Qty");
            
            // Price index BTO/STO quotes references
            let priceIdx = headers.indexOf("Live");
            if (priceIdx === -1 || row[priceIdx] === "") {
                priceIdx = headers.indexOf("STC-Price-actual");
            }
            if (priceIdx === -1 || row[priceIdx] === "") {
                priceIdx = headers.indexOf("STC-Price");
            }
            if (priceIdx === -1 || row[priceIdx] === "") {
                priceIdx = headers.indexOf("Price");
            }
            
            // Parse details safely
            const trader = row[traderIdx] || "author";
            const symbol = row[symbolIdx] || "";
            const rawQty = qtyIdx !== -1 ? row[qtyIdx] : "";
            const qty = rawQty === "" ? "1" : parseInt(parseFloat(rawQty)) || "1";
            const price = priceIdx !== -1 && row[priceIdx] !== "" ? parseFloat(row[priceIdx]) || "0.01" : "0.01";
            
            // Determine action (BTO -> STC / STO -> BTC / default -> STC)
            const typeIdx = headers.indexOf("Type");
            let action = "STC";
            if (typeIdx !== -1) {
                const typeVal = row[typeIdx];
                if (typeVal === "BTO") action = "STC";
                else if (typeVal === "STO") action = "BTC";
            }
            
            // Overwrite Manual Qty Box
            document.getElementById("qt-qty").value = qty;
            
            // Re-format Alert String Option/Stock details
            let alertMsg = "";
            if (symbol.includes("_")) {
                // option format symbol (e.g. AAPL_230616C150)
                // regex exp to match options parts
                const match = symbol.match(/(\w+)_(\d{6})([CP])([\d.]+)/i);
                if (match) {
                    const [, symName, expDate, opType, strike] = match;
                    // convert expDate standard format mm/dd
                    const formattedDate = `${expDate.substring(0, 2)}/${expDate.substring(2, 4)}`;
                    alertMsg = `${trader}, ${action} ${qty} ${symName} ${strike}${opType} ${formattedDate} @${price}`;
                } else {
                    alertMsg = `${trader}, ${action} ${qty} ${symbol} @${price}`;
                }
            } else {
                alertMsg = `${trader}, ${action} ${qty} ${symbol} @${price}`;
            }
            
            // Prefill Inputs
            document.getElementById("qt-message").value = alertMsg;
            document.getElementById("qt-current-trade").innerHTML = `
                <strong>${action} ${qty} ${symbol} @ ${price}</strong><br>
                <span style="color: var(--text-muted)">Author: ${trader}</span>
            `;
        } catch (e) {
            console.error("Prefill row parsing error:", e);
        }
    };

    // Helper functions
    const getSelectValues = (select) => {
        const result = [];
        const options = select && select.options;
        if (!options) return "All";
        for (let i = 0; i < options.length; i++) {
            const opt = options[i];
            if (opt.selected) {
                result.push(opt.value || opt.text);
            }
        }
        return result.length === 0 || result.includes("All") ? "All" : result;
    };

    // Initial load first active tab
    loadTabData("dashboard");
});
