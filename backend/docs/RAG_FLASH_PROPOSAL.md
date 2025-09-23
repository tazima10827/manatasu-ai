# RAG + Gemini Flash システム設計書

## 1. システム概要

### アーキテクチャ
```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Flutter   │────▶│   FastAPI    │────▶│  Vertex AI      │
│   Frontend  │     │   Backend    │     │  Gemini Flash   │
└─────────────┘     └──────────────┘     └─────────────────┘
                            │                      │
                            ▼                      ▼
                    ┌──────────────┐     ┌─────────────────┐
                    │  Firestore   │     │ Vector Search   │
                    │  Database    │     │   Embeddings    │
                    └──────────────┘     └─────────────────┘
```

## 2. RAGシステム設計

### 2.1 データ準備フェーズ

#### データソース
- **文部科学省指導要領**: PDF形式、約500ページ
- **教科書データ**: 各教科・学年別、約3,000ページ
- **過去の生成問題**: 約10,000問
- **参考書・問題集**: 約2,000ページ

#### エンベディング戦略
```python
# チャンク戦略
CHUNK_SIZE = 1000  # トークン数
CHUNK_OVERLAP = 200  # オーバーラップ
EMBEDDING_MODEL = "text-embedding-005"  # 最新の多言語対応モデル
```

### 2.2 検索フェーズ

#### ハイブリッド検索
1. **ベクトル検索**: 意味的類似度
2. **キーワード検索**: BM25アルゴリズム
3. **メタデータフィルター**: 教科、学年、難易度

```python
def hybrid_search(query: str, filters: dict) -> List[Document]:
    # 1. ベクトル検索（70%重み）
    vector_results = vector_search(query, top_k=20)

    # 2. キーワード検索（30%重み）
    keyword_results = keyword_search(query, top_k=20)

    # 3. 結果を統合・再ランキング
    combined = rerank_results(vector_results, keyword_results)

    # 4. メタデータフィルター適用
    filtered = apply_filters(combined, filters)

    return filtered[:10]  # Top 10を返す
```

### 2.3 生成フェーズ

#### プロンプトテンプレート
```python
RAG_PROMPT_TEMPLATE = """
あなたは日本の教育専門家です。以下の参考情報を基に、
学習指導要領に準拠した問題を生成してください。

【参考情報】
{context}

【生成条件】
- 教科: {subject}
- 学年: {grade}
- 難易度: {difficulty}
- 問題数: {count}

【要求事項】
1. 学習指導要領の目標に沿った内容
2. 発達段階に適した表現
3. 思考力・判断力・表現力を育成
4. 参考情報の出典を明記

【出力形式】
JSON形式で出力してください。
"""
```

## 3. Gemini Flash 最適化

### 3.1 モデル選択
```python
# Gemini 1.5 Flash-002 (最新版)
MODEL_CONFIG = {
    "model": "gemini-1.5-flash-002",
    "temperature": 0.7,  # 創造性と正確性のバランス
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
    "response_mime_type": "application/json"  # JSON出力を強制
}
```

### 3.2 コンテキストウィンドウ管理
- **最大コンテキスト**: 1M トークン（Gemini 1.5 Flash）
- **推奨使用量**: 32K トークン（コストと速度のバランス）
- **内訳**:
  - システムプロンプト: 1K トークン
  - RAG検索結果: 20K トークン
  - ユーザー入力: 1K トークン
  - 予備: 10K トークン

### 3.3 キャッシング戦略
```python
# Vertex AI Context Caching
CACHE_CONFIG = {
    "cache_duration": 3600,  # 1時間
    "cache_key_prefix": "manatasu_rag_",
    "max_cache_size": 100  # 最大100エントリ
}

# 頻繁に使用される指導要領データをキャッシュ
CACHED_CONTEXTS = [
    "elementary_math_guidelines",
    "elementary_japanese_guidelines",
    "junior_math_guidelines"
]
```

## 4. コスト分析

### 4.1 初期構築コスト

| 項目 | 数量 | 単価 | 合計 |
|------|------|------|------|
| **データ準備** | | | |
| PDF処理・テキスト抽出 | 10,000ページ | $0.001/ページ | $10 |
| エンベディング生成 | 50,000チャンク | $0.00004/1Kトークン | $80 |
| Vector Searchインデックス | 1インデックス | $100/月 | $100 |
| **合計（初期）** | | | **$190** |

### 4.2 月間運用コスト（想定利用量）

| 項目 | 月間使用量 | 単価 | 月額 |
|------|------------|------|------|
| **Gemini Flash API** | | | |
| 入力トークン | 10M トークン | $0.00005/1Kトークン | $0.50 |
| 出力トークン | 2M トークン | $0.00015/1Kトークン | $0.30 |
| Context Caching | 5M トークン | $0.000025/1Kトークン | $0.13 |
| **Vector Search** | | | |
| クエリ実行 | 10,000クエリ | $0.001/クエリ | $10 |
| インデックス維持 | 1インデックス | $100/月 | $100 |
| **Cloud Run** | | | |
| CPU時間 | 100時間 | $0.084/時間 | $8.40 |
| メモリ | 4GB×100時間 | $0.009/GB時間 | $3.60 |
| **Firestore** | | | |
| 読み取り | 100,000回 | $0.036/10万回 | $0.04 |
| 書き込み | 10,000回 | $0.108/10万回 | $0.01 |
| ストレージ | 10GB | $0.108/GB | $1.08 |
| **合計（月額）** | | | **$124.06** |

### 4.3 利用規模別コスト予測

| 利用規模 | 月間問題生成数 | 月間ユーザー数 | 推定月額 |
|----------|---------------|---------------|----------|
| Small | 1,000問 | 100人 | $50 |
| Medium | 10,000問 | 1,000人 | $124 |
| Large | 50,000問 | 5,000人 | $450 |
| Enterprise | 200,000問 | 20,000人 | $1,500 |

## 5. 実装ロードマップ

### Phase 1: 基本RAG実装（2週間）
- [ ] Vector Searchセットアップ
- [ ] エンベディング生成パイプライン
- [ ] 基本的な検索機能
- [ ] Gemini Flash統合

### Phase 2: 最適化（2週間）
- [ ] ハイブリッド検索実装
- [ ] Context Caching導入
- [ ] プロンプト最適化
- [ ] レスポンス時間改善

### Phase 3: 高度な機能（3週間）
- [ ] 適応型チャンク戦略
- [ ] リランキングモデル
- [ ] フィードバックループ
- [ ] A/Bテスト機能

### Phase 4: スケーラビリティ（2週間）
- [ ] 負荷分散
- [ ] キャッシュ最適化
- [ ] コスト監視ダッシュボード
- [ ] 自動スケーリング

## 6. パフォーマンス目標

| メトリクス | 目標値 | 現状 |
|------------|--------|------|
| レスポンス時間 | < 3秒 | 5秒 |
| 検索精度（MRR） | > 0.85 | - |
| 生成品質スコア | > 4.5/5.0 | - |
| システム稼働率 | > 99.9% | - |
| コスト効率 | < $0.01/問題 | - |

## 7. リスクと対策

### リスク1: コスト超過
**対策**:
- 使用量アラート設定
- 自動スケールダウン
- キャッシュ積極活用

### リスク2: レスポンス遅延
**対策**:
- 並列処理の実装
- エッジキャッシング
- インデックス最適化

### リスク3: 品質低下
**対策**:
- 定期的な品質評価
- フィードバック収集
- モデル再トレーニング

## 8. 推奨構成

### 最小構成（MVP）
```yaml
components:
  - Gemini Flash API (Pay-as-you-go)
  - Firestore (Free tier)
  - Cloud Run (1 instance)
  - Basic Vector Search

monthly_cost: ~$50
suitable_for: POC, 小規模テスト
```

### 推奨構成（Production）
```yaml
components:
  - Gemini Flash API with Context Caching
  - Firestore (Standard)
  - Cloud Run (2-4 instances, auto-scaling)
  - Optimized Vector Search
  - Cloud CDN

monthly_cost: ~$150-200
suitable_for: 本番環境、中規模利用
```

### エンタープライズ構成
```yaml
components:
  - Gemini Flash + Fine-tuned models
  - Firestore (Multi-region)
  - Cloud Run (10+ instances, global)
  - Advanced Vector Search with ML ranking
  - Cloud CDN + Load Balancer
  - Monitoring & Analytics

monthly_cost: ~$1,500-3,000
suitable_for: 大規模展開、SLA保証
```

## 9. 実装サンプル

### RAGパイプライン実装例
```python
class OptimizedRAGPipeline:
    def __init__(self):
        self.vector_store = VectorStore()
        self.cache = ContextCache()
        self.model = GenerativeModel("gemini-1.5-flash-002")

    async def generate_with_rag(self, query: dict) -> dict:
        # 1. キャッシュチェック
        cache_key = self._generate_cache_key(query)
        if cached := await self.cache.get(cache_key):
            return cached

        # 2. 並列検索
        search_tasks = [
            self.vector_store.search(query["topic"]),
            self.search_guidelines(query["grade"]),
            self.search_similar_problems(query)
        ]
        contexts = await asyncio.gather(*search_tasks)

        # 3. コンテキスト構築
        prompt = self.build_optimized_prompt(query, contexts)

        # 4. 生成（ストリーミング）
        response = await self.model.generate_content_stream(
            prompt,
            generation_config=MODEL_CONFIG
        )

        # 5. キャッシュ保存
        await self.cache.set(cache_key, response, ttl=3600)

        return response
```

## 10. まとめ

### 投資対効果（ROI）
- **初期投資**: $190
- **月間運用**: $124
- **期待効果**:
  - 問題生成時間: 80%削減
  - 生成品質: 40%向上
  - 運用コスト: 60%削減（手動作成比）

### 次のステップ
1. POC環境の構築（1週間）
2. パイロットテスト（2週間）
3. 段階的な本番移行（1ヶ月）
4. 継続的な最適化

---
*最終更新: 2025年1月*