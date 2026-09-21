import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  BookOpen,
  Building2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  FileSearch,
  FileText,
  History,
  Info,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Search,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";

// In development, Vite forwards /api requests to FastAPI on port 9000.
const API_URL = import.meta.env.VITE_API_URL || "/api";
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];
const DEFAULT_CUSTOMERS_AMOUNT = 100;
const CUSTOMERS_SIZE_OPTIONS = [100, 500, 1000];
const CUSTOMER_SORT_OPTIONS = [
  { value: "score_desc", label: "Score: high to low" },
  { value: "score_asc", label: "Score: low to high" },
  { value: "customer_id_asc", label: "Customer ID" },
];
const TAB_TITLES = {
  overview: "Risk overview",
  investigations: "Past investigations",
  policies: "Current policies",
  about: "About this demo",
};

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function displayName(customer) {
  return customer.synthetic_display_name || `Customer ${customer.customer_id}`;
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

// The API does not expose sex yet. This stable fallback keeps the temporary
// synthetic profile data consistent across refreshes.
function customerSex(customer) {
  if (customer.sex) return customer.sex.toLowerCase();
  const hash = [...customer.customer_id].reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  );
  return hash % 2 === 0 ? "female" : "male";
}

function customerIdFromUrl() {
  return new URL(window.location.href).searchParams.get("customer");
}

function updateCustomerUrl(customerId, method = "pushState") {
  const url = new URL(window.location.href);
  if (customerId) url.searchParams.set("customer", customerId);
  else url.searchParams.delete("customer");
  window.history[method]({}, "", url);
}

async function api(path, options) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function App() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [investigation, setInvestigation] = useState(null);
  const [pastInvestigations, setPastInvestigations] = useState([]);
  const [selectedPastInvestigation, setSelectedPastInvestigation] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState(null);
  const [riskDetail, setRiskDetail] = useState(null);
  const [search, setSearch] = useState("");
  const [sex, setSex] = useState("all");
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [customersAmount, setCustomersAmount] = useState(DEFAULT_CUSTOMERS_AMOUNT);
  const [customerSort, setCustomerSort] = useState("score_desc");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [investigationsLoading, setInvestigationsLoading] = useState(false);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError("");
    const separator = customerSort.lastIndexOf("_");
    const sortBy = customerSort.slice(0, separator);
    const sortOrder = customerSort.slice(separator + 1);
    api(
      `/customers/?limit=${customersAmount}&sort_by=${sortBy}&sort_order=${sortOrder}`,
      { signal: controller.signal },
    )
      .then((data) => {
        setCustomers(data);
        if (!data.length) return;

        const requestedCustomerId = customerIdFromUrl();
        const requestedCustomer = data.find(
          (customer) => customer.customer_id === requestedCustomerId,
        );
        const initialCustomer = requestedCustomer || data[0];
        setSelectedCustomer(initialCustomer);
        setPage(Math.floor(data.indexOf(initialCustomer) / DEFAULT_PAGE_SIZE) + 1);

        if (!requestedCustomer) {
          updateCustomerUrl(initialCustomer.customer_id, "replaceState");
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [customersAmount, customerSort]);

  useEffect(() => {
    function restoreCustomerFromUrl() {
      const requestedCustomerId = customerIdFromUrl();
      const requestedCustomer = customers.find(
        (customer) => customer.customer_id === requestedCustomerId,
      );
      if (requestedCustomer) setSelectedCustomer(requestedCustomer);
    }

    window.addEventListener("popstate", restoreCustomerFromUrl);
    return () => window.removeEventListener("popstate", restoreCustomerFromUrl);
  }, [customers]);

  useEffect(() => {
    if (!selectedCustomer) return;
    const controller = new AbortController();
    setDetailLoading(true);
    setInvestigation(null);
    setRiskDetail(null);
    const customerId = encodeURIComponent(selectedCustomer.customer_id);
    api(`/customers/${customerId}/transactions?limit=100`, { signal: controller.signal })
      .then(setTransactions)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    api(`/customers/${customerId}/risk`, { signal: controller.signal })
      .then(setRiskDetail)
      .catch((err) => {
        if (err.name !== "AbortError" && err.status !== 404) setError(err.message);
      });
    api(`/customers/${customerId}/investigations/latest`, { signal: controller.signal })
      .then((cached) => pollInvestigation(cached, controller.signal))
      .catch((err) => {
        if (err.name !== "AbortError" && err.status !== 404) setError(err.message);
      });

    return () => controller.abort();
  }, [selectedCustomer]);

  useEffect(() => {
    if (activeTab !== "investigations") return;
    const controller = new AbortController();
    setInvestigationsLoading(true);
    api("/investigations/?limit=200", { signal: controller.signal })
      .then(async (items) => {
        setPastInvestigations(items);
        if (!items.length) {
          setSelectedPastInvestigation(null);
          return;
        }
        const selectedStillExists = items.some(
          (item) => item.investigation_id === selectedPastInvestigation?.investigation_id,
        );
        if (!selectedStillExists) {
          const full = await api(`/investigations/${items[0].investigation_id}`, {
            signal: controller.signal,
          });
          setSelectedPastInvestigation(full);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setInvestigationsLoading(false);
      });

    return () => controller.abort();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "policies") return;
    const controller = new AbortController();
    setPoliciesLoading(true);
    api("/policies/", { signal: controller.signal })
      .then((documents) => {
        setPolicies(documents);
        setSelectedPolicyId((current) => (
          documents.some((document) => document.document_id === current)
            ? current
            : documents[0]?.document_id || null
        ));
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPoliciesLoading(false);
      });

    return () => controller.abort();
  }, [activeTab]);

  const filteredCustomers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return customers.filter((customer) => {
      const matchesSearch =
        !query ||
        displayName(customer).toLowerCase().includes(query) ||
        customer.customer_id.toLowerCase().includes(query);
      const matchesSex = sex === "all" || customerSex(customer) === sex;
      return matchesSearch && matchesSex;
    });
  }, [customers, search, sex]);

  const pageCount = Math.max(1, Math.ceil(filteredCustomers.length / pageSize));
  const paginatedCustomers = filteredCustomers.slice(
    (page - 1) * pageSize,
    page * pageSize,
  );
  const firstVisibleCustomer = filteredCustomers.length ? (page - 1) * pageSize + 1 : 0;
  const lastVisibleCustomer = Math.min(page * pageSize, filteredCustomers.length);
  const selectedPolicy = policies.find(
    (policy) => policy.document_id === selectedPolicyId,
  ) || null;

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const totalAccounts = customers.reduce(
    (total, customer) => total + customer.accounts.length,
    0,
  );
  const totalBalance = customers.reduce(
    (total, customer) =>
      total + customer.accounts.reduce((sum, account) => sum + Number(account.init_balance), 0),
    0,
  );

  async function startInvestigation() {
    if (!selectedCustomer) return;
    setInvestigating(true);
    setError("");
    try {
      const result = await api(
        `/investigate/${encodeURIComponent(selectedCustomer.customer_id)}`,
        { method: "POST" },
      );
      await pollInvestigation(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setInvestigating(false);
    }
  }

  async function pollInvestigation(initial, signal) {
    let result = initial;
    setInvestigation(result);
    const deadline = Date.now() + 60_000;
    while (
      ["pending", "in_progress"].includes(result.status)
      && Date.now() < deadline
      && !signal?.aborted
    ) {
      await new Promise((resolve) => window.setTimeout(resolve, 1_500));
      result = await api(`/investigations/${result.investigation_id}`, { signal });
      setInvestigation(result);
    }
    return result;
  }

  function selectCustomer(customer) {
    setSelectedCustomer(customer);
    updateCustomerUrl(customer.customer_id);
  }

  async function selectPastInvestigation(item) {
    setError("");
    try {
      const full = await api(`/investigations/${item.investigation_id}`);
      setSelectedPastInvestigation(full);
    } catch (err) {
      setError(err.message);
    }
  }

  function showTab(tab) {
    setActiveTab(tab);
    setMobileNavOpen(false);
  }

  function openPolicy(documentId) {
    setSelectedPolicyId(documentId);
    showTab("policies");
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNavOpen ? "sidebar--open" : ""}`}>
        <div className="brand">
          <div className="brand__mark"><ShieldCheck size={22} /></div>
          <div><strong>FinGuard</strong><span>AI</span></div>
          <button className="icon-button sidebar__close" onClick={() => setMobileNavOpen(false)}>
            <X size={20} />
          </button>
        </div>
        <nav>
          <p className="nav-label">Workspace</p>
          <button
            className={`nav-item ${activeTab === "overview" ? "nav-item--active" : ""}`}
            onClick={() => showTab("overview")}
          >
            <LayoutDashboard size={19} /> Overview
          </button>
          <button
            className={`nav-item ${activeTab === "investigations" ? "nav-item--active" : ""}`}
            onClick={() => showTab("investigations")}
          >
            <History size={19} /> Past investigations
          </button>
          <button
            className={`nav-item ${activeTab === "policies" ? "nav-item--active" : ""}`}
            onClick={() => showTab("policies")}
          >
            <BookOpen size={19} /> Policies
          </button>
          <button
            className={`nav-item ${activeTab === "about" ? "nav-item--active" : ""}`}
            onClick={() => showTab("about")}
          >
            <Info size={19} /> About this demo
          </button>
        </nav>
        {/* <div className="sidebar__status">
          <span className="status-dot" />
          <div><strong>API connection</strong><small>{API_URL}</small></div>
        </div> */}
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setMobileNavOpen(true)}>
            <Menu size={21} />
          </button>
          <div>
            <p className="eyebrow">Compliance workspace</p>
            <h1>{TAB_TITLES[activeTab]}</h1>
          </div>
        </header>

        <div className="page" id="dashboard" hidden={activeTab !== "overview"}>
          {error && (
            <div className="error-banner">
              <strong>Something went wrong.</strong> {error}
              <button onClick={() => setError("")}><X size={17} /></button>
            </div>
          )}

          <section className="welcome">
            <div>
              <span className="section-kicker"><Activity size={15} /> Live Demo</span>
              <h2>Explore a synthetic<br />investigation workflow.</h2>
              <p>Review customer activity and open an investigation. All data is made for this demo; a sleeping backend may take a moment to respond.</p>
              <button className="welcome__about-link" onClick={() => showTab("about")}>What is this demo? <ChevronRight size={15} /></button>
            </div>
            <div className="welcome__seal"><ShieldCheck size={48} /></div>
          </section>

          <section className="stats-grid" aria-label="Summary metrics">
            <Metric icon={<Users />} label="Customers" value={loading ? "—" : customers.length} note="loaded profiles" />
            <Metric icon={<Building2 />} label="Accounts" value={loading ? "—" : totalAccounts} note="linked accounts" />
            <Metric icon={<CircleDollarSign />} label="Opening balance" value={loading ? "—" : formatMoney(totalBalance)} note="across loaded accounts" />
          </section>

          <section className="workspace-grid" id="customers">
            <div className="panel customer-panel">
              <div className="panel__header">
                <div><p className="eyebrow">Customer directory</p><h3>Profiles</h3></div>
                <span className="count-pill">{filteredCustomers.length}</span>
              </div>
              <div className="customer-filters">
                <label className="search-box">
                  <Search size={18} />
                  <input
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Search name or ID"
                    aria-label="Search customers by name or ID"
                  />
                </label>
                <div className="filter-row">
                  <label>
                    <span>Sort</span>
                    <select
                      value={customerSort}
                      onChange={(event) => {
                        setCustomerSort(event.target.value);
                        setPage(1);
                      }}
                      aria-label="Sort customers"
                    >
                      {CUSTOMER_SORT_OPTIONS.map((option) => (
                        <option value={option.value} key={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Sex</span>
                    <select
                      value={sex}
                      onChange={(event) => {
                        setSex(event.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="all">All</option>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                    </select>
                  </label>
                  <label>
                    <span>Show</span>
                    <select
                      value={pageSize}
                      onChange={(event) => {
                        setPageSize(Number(event.target.value));
                        setPage(1);
                      }}
                    >
                      {PAGE_SIZE_OPTIONS.map((option) => (
                        <option value={option} key={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Customers</span>
                    <select
                      value={customersAmount}
                      onChange={(event) => {
                        setCustomersAmount(Number(event.target.value));
                        setPage(1);
                      }}
                    >
                      {CUSTOMERS_SIZE_OPTIONS.map((option) => (
                        <option value={option} key={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
              <div className="customer-list">
                {loading ? (
                  <Loading label="Loading customers" />
                ) : filteredCustomers.length ? (
                  paginatedCustomers.map((customer) => (
                    <button
                      className={`customer-row ${selectedCustomer?.customer_id === customer.customer_id ? "customer-row--active" : ""}`}
                      key={customer.customer_id}
                      onClick={() => selectCustomer(customer)}
                      aria-current={selectedCustomer?.customer_id === customer.customer_id ? "true" : undefined}
                    >
                      <span className="customer-avatar">{displayName(customer).slice(0, 2).toUpperCase()}</span>
                      <span className="customer-row__text">
                        <strong>{displayName(customer)}</strong>
                        <small>{customer.customer_id} · {customerSex(customer)} · {customer.accounts.length} account{customer.accounts.length === 1 ? "" : "s"}</small>
                      </span>
                      <span className={`customer-score customer-score--${customer.risk?.risk_band || "unscored"}`}>
                        {customer.risk && customer.risk.risk_band !== "unscored"
                          ? Math.round(Number(customer.risk.score))
                          : "—"}
                      </span>
                      <ChevronRight size={18} />
                    </button>
                  ))
                ) : (
                  <EmptyState title="No customers found" text="Try adjusting the search or sex filter." />
                )}
              </div>
              {!loading && filteredCustomers.length > 0 && (
                <div className="pagination" aria-label="Customer pagination">
                  <span>{firstVisibleCustomer}–{lastVisibleCustomer} of {filteredCustomers.length}</span>
                  <div>
                    <button
                      className="pagination__button"
                      onClick={() => setPage((current) => Math.max(1, current - 1))}
                      disabled={page === 1}
                      aria-label="Previous customer page"
                    >
                      <ChevronLeft size={17} />
                    </button>
                    <span>Page {page} of {pageCount}</span>
                    <button
                      className="pagination__button"
                      onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                      disabled={page === pageCount}
                      aria-label="Next customer page"
                    >
                      <ChevronRight size={17} />
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="panel detail-panel">
              {selectedCustomer ? (
                <>
                  <div className="profile-header">
                    <div className="profile-header__identity">
                      <span className="profile-avatar">{displayName(selectedCustomer).slice(0, 2).toUpperCase()}</span>
                      <div><p className="eyebrow">Customer profile</p><h3>{displayName(selectedCustomer)}</h3><span className="mono-id">{selectedCustomer.customer_id} · {customerSex(selectedCustomer)}</span></div>
                    </div>
                    <button className="primary-button" onClick={startInvestigation} disabled={investigating}>
                      {investigating ? <LoaderCircle className="spin" size={18} /> : <FileSearch size={18} />}
                      {investigating ? "Starting…" : "Investigate"}
                    </button>
                  </div>

                  <div className="account-strip">
                    {selectedCustomer.accounts.map((account) => (
                      <div className="account-card" key={account.account_id}>
                        <div><span>{account.account_type}</span><strong>•••• {String(account.account_id).slice(-4)}</strong></div>
                        <div><small>{account.country}</small><b>{formatMoney(account.init_balance)}</b></div>
                      </div>
                    ))}
                    {!selectedCustomer.accounts.length && <p className="muted">No linked accounts.</p>}
                  </div>

                  {selectedCustomer.risk && selectedCustomer.risk.risk_band !== "unscored" ? (
                    <section className="risk-card" aria-label="Operational risk score">
                      <div className="risk-card__score">
                        <span>Operational risk</span>
                        <strong>{Math.round(Number(selectedCustomer.risk.score))}</strong>
                        <b className={`risk-band risk-band--${selectedCustomer.risk.risk_band}`}>
                          {selectedCustomer.risk.risk_band}
                        </b>
                      </div>
                      <div className="risk-card__evidence">
                        <small>
                          Cutoff step {selectedCustomer.risk.data_cutoff_step} · {selectedCustomer.risk.model_version}
                        </small>
                        {(selectedCustomer.risk.evidence.top_factors || []).slice(0, 3).map((factor) => (
                          <p key={factor}>{factor}</p>
                        ))}
                        {riskDetail?.policy_sources?.length > 0 && (
                          <div className="policy-sources">
                            <span>Relevant internal policy</span>
                            {riskDetail.policy_sources.slice(0, 3).map((source) => (
                              <button
                                className="policy-source-link"
                                key={source.source_id}
                                onClick={() => openPolicy(source.document_id)}
                              >
                                <span>
                                  <strong>{source.title} v{source.version}</strong>
                                  <small>{source.heading}</small>
                                </span>
                                <ChevronRight size={14} />
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </section>
                  ) : (
                    <div className="unscored-note">
                      Risk status: unscored. Run the batch scorer after importing data.
                    </div>
                  )}

                  {investigation && (
                    <div className="investigation-result" id="investigation">
                      <ShieldCheck size={21} />
                      <div>
                        <strong>Investigation #{investigation.investigation_id}</strong>
                        <p>Status: <span>{investigation.status}</span>{investigation.summary ? ` · ${investigation.summary}` : " · Analysis is queued."}</p>
                        {investigation.evidence?.result && (
                          <div className="investigation-details">
                            {investigation.evidence.result.risk_factors?.length > 0 && (
                              <section>
                                <b>Risk factors</b>
                                <ul>{investigation.evidence.result.risk_factors.map((item) => (
                                  <li key={`${item.factor}-${item.evidence_ids.join("-")}`}>{item.factor}</li>
                                ))}</ul>
                              </section>
                            )}
                            <section>
                              <b>Recommended next steps</b>
                              <ul>{investigation.evidence.result.recommended_next_steps.map((item) => (
                                <li key={item}>{item}</li>
                              ))}</ul>
                            </section>
                            <small>
                              Narrative: {investigation.evidence.generation_mode === "deepseek" ? "DeepSeek" : "deterministic fallback"}
                            </small>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="transactions-header">
                    <div><p className="eyebrow">Recent activity</p><h4>Transactions</h4></div>
                    <span>{transactions.length} records</span>
                  </div>
                  <div className="transaction-table-wrap">
                    {detailLoading ? (
                      <Loading label="Loading transactions" />
                    ) : transactions.length ? (
                      <table>
                        <thead><tr><th>Transaction</th><th>Type</th><th>Direction</th><th>Step</th><th className="align-right">Amount</th></tr></thead>
                        <tbody>
                          {transactions.map((transaction) => {
                            const accountIds = selectedCustomer.accounts.map((account) => account.account_id);
                            const outgoing = accountIds.includes(transaction.sender_account_id);
                            return (
                              <tr key={transaction.tx_id}>
                                <td><strong>#{transaction.tx_id}</strong><small>{transaction.sender_account_id} → {transaction.receiver_account_id}</small></td>
                                <td><span className="type-pill">{transaction.tx_type}</span></td>
                                <td><span className={outgoing ? "direction direction--out" : "direction direction--in"}>{outgoing ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}{outgoing ? "Outgoing" : "Incoming"}</span></td>
                                <td>{transaction.simulation_step}</td>
                                <td className="align-right amount">{formatMoney(transaction.tx_amount)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    ) : (
                      <EmptyState title="No transaction activity" text="This customer has no transactions to review." />
                    )}
                  </div>
                </>
              ) : (
                <EmptyState title="Select a customer" text="Choose a profile to review accounts and transaction activity." />
              )}
            </div>
          </section>
        </div>

        <div className="page" id="investigations" hidden={activeTab !== "investigations"}>
          {error && (
            <div className="error-banner">
              <strong>Something went wrong.</strong> {error}
              <button onClick={() => setError("")}><X size={17} /></button>
            </div>
          )}
          <section className="history-heading">
            <div>
              <p className="eyebrow">Cached results</p>
              <h2>Past investigations</h2>
              <p>Completed and in-progress investigations are stored and reused for unchanged risk snapshots.</p>
            </div>
            <span className="count-pill">{pastInvestigations.length}</span>
          </section>

          <section className="history-grid">
            <div className="panel history-list-panel">
              <div className="panel__header">
                <div><p className="eyebrow">History</p><h3>Investigations</h3></div>
              </div>
              <div className="history-list">
                {investigationsLoading ? (
                  <Loading label="Loading investigations" />
                ) : pastInvestigations.length ? (
                  pastInvestigations.map((item) => (
                    <button
                      className={`history-row ${selectedPastInvestigation?.investigation_id === item.investigation_id ? "history-row--active" : ""}`}
                      key={item.investigation_id}
                      onClick={() => selectPastInvestigation(item)}
                    >
                      <span className="history-row__icon"><FileSearch size={17} /></span>
                      <span className="history-row__text">
                        <strong>Investigation #{item.investigation_id}</strong>
                        <small>{item.customer_id} · {formatDate(item.updated_at)}</small>
                      </span>
                      <span className={`status-pill status-pill--${item.status}`}>{item.status}</span>
                    </button>
                  ))
                ) : (
                  <EmptyState title="No investigations yet" text="Start an investigation from the customer overview." />
                )}
              </div>
            </div>

            <div className="panel history-detail-panel">
              {selectedPastInvestigation ? (
                <InvestigationDetail investigation={selectedPastInvestigation} />
              ) : (
                <EmptyState title="Select an investigation" text="Choose a cached investigation to review its result." />
              )}
            </div>
          </section>
        </div>

        <div className="page" id="policies" hidden={activeTab !== "policies"}>
          {error && (
            <div className="error-banner">
              <strong>Something went wrong.</strong> {error}
              <button onClick={() => setError("")}><X size={17} /></button>
            </div>
          )}
          <section className="history-heading">
            <div>
              <p className="eyebrow">Policy corpus</p>
              <h2>Current policies</h2>
              <p>Review the source documents used to support operational risk investigations.</p>
            </div>
            <span className="count-pill">{policies.length}</span>
          </section>

          <section className="policy-library-grid">
            <div className="panel policy-list-panel">
              <div className="panel__header">
                <div><p className="eyebrow">In effect</p><h3>Documents</h3></div>
              </div>
              <div className="policy-list">
                {policiesLoading ? (
                  <Loading label="Loading policies" />
                ) : policies.length ? (
                  policies.map((policy) => (
                    <button
                      className={`policy-row ${selectedPolicyId === policy.document_id ? "policy-row--active" : ""}`}
                      key={policy.document_id}
                      onClick={() => setSelectedPolicyId(policy.document_id)}
                    >
                      <span className="history-row__icon"><FileText size={17} /></span>
                      <span className="policy-row__text">
                        <strong>{policy.title}</strong>
                        <small>v{policy.version} · {policy.category}</small>
                      </span>
                      <ChevronRight size={16} />
                    </button>
                  ))
                ) : (
                  <EmptyState title="No current policies" text="No active policy documents are available." />
                )}
              </div>
            </div>

            <div className="panel policy-document-panel">
              {selectedPolicy ? (
                <PolicyDocument policy={selectedPolicy} />
              ) : (
                <EmptyState title="Select a policy" text="Choose a source document to read it here." />
              )}
            </div>
          </section>
        </div>

        <div className="page about-page" id="about" hidden={activeTab !== "about"}>
          <section className="about-hero">
            <div>
              <span className="section-kicker"><Info size={15} /> Portfolio demo</span>
              <h2>A hands-on example of a financial transaction review workflow.</h2>
              <p>
                FinGuardAI brings together a customer dashboard, transaction risk scoring,
                sample policy references, and investigation summaries. It is here for
                visitors to explore the work behind the project.
              </p>
              <button className="primary-button" onClick={() => showTab("overview")}>Explore customers <ChevronRight size={17} /></button>
            </div>
            <div className="about-hero__badge">
              <ShieldCheck size={28} />
              <strong>Sample data only</strong>
              <span>No real customer information is shown.</span>
            </div>
          </section>

          <section className="about-section" aria-labelledby="about-try-heading">
            <p className="eyebrow">Try the demo</p>
            <h3 id="about-try-heading">A simple path through the app</h3>
            <div className="about-steps">
              <article className="panel about-step">
                <span>01</span>
                <h4>Choose a customer</h4>
                <p>Browse synthetic accounts and transactions on the Overview page. Where available, a saved score helps prioritize what to review.</p>
              </article>
              <article className="panel about-step">
                <span>02</span>
                <h4>Open an investigation</h4>
                <p>See a summary of existing evidence, relevant sample policies, risk factors, and suggested next steps.</p>
              </article>
              <article className="panel about-step">
                <span>03</span>
                <h4>Explore the sources</h4>
                <p>Read saved investigations and the policy documents that provide context for the explanations.</p>
              </article>
            </div>
          </section>

          <section className="about-details">
            <article className="panel about-detail">
              <p className="eyebrow">What it demonstrates</p>
              <h3>From data to a readable review</h3>
              <p>A Python backend imports synthetic transactions, scores activity with a local model, retrieves relevant policy passages, and stores investigation results. The React interface makes the workflow easy to explore.</p>
              <p>The public interface can run on Cloudflare Pages. Its interactive API and database run separately.</p>
            </article>
            <article className="panel about-detail">
              <p className="eyebrow">Demo boundaries</p>
              <h3>A showcase, not a decision system</h3>
              <p>Customers and transactions are synthetic, and the policies are examples. A score is a review priority, not a finding of fraud.</p>
              <p>DeepSeek may help word an explanation when configured. A deterministic summary is used otherwise. A human would make any real-world decision.</p>
            </article>
          </section>
        </div>
      </main>
    </div>
  );
}

function InvestigationDetail({ investigation }) {
  const result = investigation.evidence?.result;
  const risk = investigation.evidence?.risk_snapshot;
  return (
    <>
      <div className="history-detail-header">
        <div>
          <p className="eyebrow">Investigation #{investigation.investigation_id}</p>
          <h3>{investigation.customer_id}</h3>
          <small>{formatDate(investigation.updated_at)}</small>
        </div>
        <span className={`status-pill status-pill--${investigation.status}`}>{investigation.status}</span>
      </div>
      {risk && (
        <div className="history-risk-summary">
          <span>Operational score</span>
          <strong>{Math.round(Number(risk.score))}</strong>
          <b className={`risk-band risk-band--${risk.risk_band}`}>{risk.risk_band}</b>
        </div>
      )}
      <p className="history-summary">{investigation.summary || "No summary is available."}</p>
      {result && (
        <div className="history-sections">
          {result.risk_factors?.length > 0 && (
            <section><h4>Risk factors</h4><ul>{result.risk_factors.map((item) => (
              <li key={`${item.factor}-${item.evidence_ids.join("-")}`}>{item.factor}</li>
            ))}</ul></section>
          )}
          {result.relevant_rules?.length > 0 && (
            <section><h4>Relevant rules</h4><ul>{result.relevant_rules.map((item) => (
              <li key={`${item.rule}-${item.source_ids.join("-")}`}>{item.rule}</li>
            ))}</ul></section>
          )}
          <section><h4>Recommended next steps</h4><ul>{result.recommended_next_steps.map((item) => (
            <li key={item}>{item}</li>
          ))}</ul></section>
          <section><h4>Limitations</h4><ul>{result.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}</ul></section>
          <small className="history-generation-mode">
            Generated by {investigation.evidence.generation_mode === "deepseek" ? "DeepSeek" : "deterministic fallback"}
          </small>
        </div>
      )}
    </>
  );
}

function PolicyDocument({ policy }) {
  return (
    <article className="policy-document">
      <header>
        <p className="eyebrow">{policy.document_id}</p>
        <h2>{policy.title}</h2>
        <div className="policy-document__metadata">
          <span>Version {policy.version}</span>
          <span>Effective {policy.effective_date}</span>
          <span>{policy.jurisdiction}</span>
        </div>
      </header>
      <div className="policy-document__content">{policy.content}</div>
    </article>
  );
}

function Metric({ icon, label, value, note }) {
  return (
    <article className="metric-card">
      <div className="metric-card__icon">{icon}</div>
      <div><p>{label}</p><strong>{value}</strong><small>{note}</small></div>
    </article>
  );
}

function Loading({ label }) {
  return <div className="loading"><LoaderCircle className="spin" size={22} /><span>{label}</span></div>;
}

function EmptyState({ title, text }) {
  return <div className="empty-state"><FileSearch size={28} /><strong>{title}</strong><p>{text}</p></div>;
}

export default App;
