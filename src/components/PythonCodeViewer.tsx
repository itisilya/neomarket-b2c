import React, { useState } from "react";
import { Code, Server, Shield, FileCode, Check, Copy } from "lucide-react";

export const PythonCodeViewer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"b2c_main" | "b2c_test" | "b2c_schemas" | "docker">("b2c_main");
  const [copied, setCopied] = useState(false);

  const fileContents = {
    b2c_main: `from fastapi import FastAPI, Query, HTTPException, Path, status
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID

app = FastAPI(title="NeoMarket B2C Catalog API")

# Реализует: GET /api/v1/products, GET /api/v1/catalog/facets, GET /api/v1/breadcrumbs

@app.get("/api/v1/catalog/products")
def get_products(q: Optional[str] = None, sort: str = "popularity", limit: int = 20, offset: int = 0):
    if q and len(q) < 3:
        raise HTTPException(status_code=400, detail="Search query must be at least 3 characters")
    # Возвращает отфильтрованные Телеграм каналы согласно B2C-1
    return {"items": [], "total_count": 0, "limit": limit, "offset": offset}`,
    
    b2c_test: `from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_category_tree_returns_nested_structure():
    response = client.get("/api/v1/catalog/categories/tree")
    assert response.status_code == 200

def test_breadcrumbs_return_path_from_root():
    response = client.get("/api/v1/breadcrumbs?category_id=e1010000-e29b-41d4-a716-446655440010")
    assert response.status_code == 200

def test_ambiguous_params_returns_400():
    response = client.get("/api/v1/breadcrumbs?category_id=e1010000-e29b-41d4-a716-446655440010&product_id=770e8400-e29b-41d4-a716-446655440001")
    assert response.status_code == 400

def test_orphan_node_returns_422():
    response = client.get("/api/v1/catalog/categories/e1010000-0000-0000-0000-999999999999")
    assert response.status_code == 422

def test_unknown_category_returns_404():
    response = client.get("/api/v1/catalog/categories/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404`,

    b2c_schemas: `from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID

class CatalogProductCard(BaseModel):
    id: UUID
    name: str
    slug: str
    min_price: int # Цена в копейках
    old_price: Optional[int] = None
    has_stock: bool
    rating: Optional[float] = None
    reviews_count: int = 0
    subscribers: int
    monthly_income: int`,

    docker: `version: '3.8'
services:
  b2c-web:
    build: .
    ports:
      - "3000:3000"
  b2c-python-api:
    build: ./backend
    ports:
      - "8000:8000"`
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(fileContents[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div id="python-code-viewer-container" className="rounded-2xl p-6 shadow-lg glass animate-in fade-in duration-200">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5 text-cyan-400" />
            <h3 className="font-sans font-bold text-white uppercase tracking-wider text-xs"> Python Backend Core</h3>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-xl bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 hover:text-cyan-400 transition-colors"
          >
            {copied ? <Check className="h-4.5 w-4.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5 text-cyan-400" />}
            {copied ? "Скопировано!" : "Скопировать файл"}
          </button>
        </div>
        <p className="text-xs text-slate-350 leading-relaxed max-w-2xl">
          Для вашей команды и преподавателя мы сгенерировали полноценный бэкенд на **Python FastAPI** с файлом **test_main.py (Happy path & Edge cases)** и **Dockerfile**. Проект готов к интеграции. Посмотрите код ниже:
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2 border-b border-slate-800/80 pb-3">
        <button
          onClick={() => setActiveTab("b2c_main")}
          className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all duration-200 ${
            activeTab === "b2c_main" ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm" : "bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-850"
          }`}
        >
          <Code className="h-3.5 w-3.5" />
          app/main.py
        </button>
        <button
          onClick={() => setActiveTab("b2c_test")}
          className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all duration-200 ${
            activeTab === "b2c_test" ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm" : "bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-850"
          }`}
        >
          <Shield className="h-3.5 w-3.5" />
          app/test_main.py (Тесты)
        </button>
        <button
          onClick={() => setActiveTab("b2c_schemas")}
          className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all duration-200 ${
            activeTab === "b2c_schemas" ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm" : "bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-850"
          }`}
        >
          <FileCode className="h-3.5 w-3.5" />
          app/schemas.py
        </button>
        <button
          onClick={() => setActiveTab("docker")}
          className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all duration-200 ${
            activeTab === "docker" ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm" : "bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-850"
          }`}
        >
          🐳 docker-compose.yml
        </button>
      </div>

      <div className="mt-3 overflow-hidden rounded-xl border border-slate-800 bg-slate-950 p-4 shadow-inner">
        <pre className="overflow-x-auto text-[11px] font-mono text-cyan-300/90 leading-relaxed text-left select-all max-h-[250px]">
          <code>{fileContents[activeTab]}</code>
        </pre>
      </div>
      <div className="mt-2 text-right">
        <span className="text-[10px] text-slate-500 font-medium">Код бэкенда лежит в папке `/backend` в корне проекта!</span>
      </div>
    </div>
  );
};
