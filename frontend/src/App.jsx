import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Building2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  FileSearch,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Search,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";

// In development, Vite forwards /api requests to FastAPI on port 8000.
const API_URL = import.meta.env.VITE_API_URL || "/api";
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

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
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function App() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [investigation, setInvestigation] = useState(null);
  const [search, setSearch] = useState("");
  const [sex, setSex] = useState("all");
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [error, setError] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    api("/customers/?limit=100")
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
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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
    setDetailLoading(true);
    setInvestigation(null);
    api(`/customers/${encodeURIComponent(selectedCustomer.customer_id)}/transactions?limit=100`)
      .then(setTransactions)
      .catch((err) => setError(err.message))
      .finally(() => setDetailLoading(false));
  }, [selectedCustomer]);

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
      setInvestigation(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setInvestigating(false);
    }
  }

  function selectCustomer(customer) {
    setSelectedCustomer(customer);
    updateCustomerUrl(customer.customer_id);
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
          <a className="nav-item nav-item--active" href="#dashboard">
            <LayoutDashboard size={19} /> Overview
          </a>
          {/* <a className="nav-item" href="#customers">
            <Users size={19} /> Customers
          </a>
          <a className="nav-item" href="#investigation">
            <FileSearch size={19} /> Investigations
          </a> */}
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
            <h1>Risk overview</h1>
          </div>
        </header>

        <div className="page" id="dashboard">
          {error && (
            <div className="error-banner">
              <strong>Something went wrong.</strong> {error}
              <button onClick={() => setError("")}><X size={17} /></button>
            </div>
          )}

          <section className="welcome">
            <div>
              <span className="section-kicker"><Activity size={15} /> Live Demo</span>
              <h2>This is a live demo<br />every piece of data is synthetic.</h2>
              <p>Review customer activity and open an investigation when something needs a closer look.</p>
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

                  {investigation && (
                    <div className="investigation-result" id="investigation">
                      <ShieldCheck size={21} />
                      <div>
                        <strong>Investigation #{investigation.investigation_id} created</strong>
                        <p>Status: <span>{investigation.status}</span>{investigation.summary ? ` · ${investigation.summary}` : " · Analysis is queued."}</p>
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
      </main>
    </div>
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
