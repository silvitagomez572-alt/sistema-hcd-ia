"""Reproducible retrieval benchmark. LLM generation is deliberately absent."""
import argparse
import json
from pathlib import Path
import numpy as np


def metrics(ranked, relevant, k):
    ranked = list(dict.fromkeys(ranked))[:k]
    relevant = set(relevant)
    if not relevant or k < 1:
        raise ValueError('Nonempty relevance labels and positive k required')
    hits = [i+1 for i, doc in enumerate(ranked) if doc in relevant]
    return {'recall': len(hits)/len(relevant), 'precision': len(hits)/k, 'rr': 1/hits[0] if hits else 0.0}


def evaluate(backend='tfidf', model_path=None):
    fixture=json.loads(Path(__file__).with_name('synthetic.json').read_text())
    docs=fixture['documents']; queries=fixture['queries']
    if backend=='tfidf':
        from sklearn.feature_extraction.text import TfidfVectorizer
        model=TfidfVectorizer(ngram_range=(1,2),lowercase=True)
        matrix=model.fit_transform([x['text'] for x in docs])
        scores=(model.transform([x['question'] for x in queries]) @ matrix.T).toarray()
    else:
        if not model_path or not Path(model_path).is_dir():
            raise ValueError('Provide an existing local embedding model; downloads are disabled')
        from sentence_transformers import SentenceTransformer
        model=SentenceTransformer(model_path,local_files_only=True,device='cpu')
        matrix=model.encode([x['text'] for x in docs],normalize_embeddings=True)
        query_vectors=model.encode([x['question'] for x in queries],normalize_embeddings=True)
        import chromadb
        from chromadb.config import Settings
        client=chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        collection=client.get_or_create_collection('synthetic_delivery_benchmark', metadata={'hnsw:space':'cosine'})
        collection.upsert(ids=[x['id'] for x in docs],embeddings=matrix.tolist(),documents=[x['text'] for x in docs])
        rankings=collection.query(query_embeddings=query_vectors.tolist(),n_results=len(docs))['ids']
        scores=np.array([[len(docs)-ranked.index(d['id']) for d in docs] for ranked in rankings])
    output={'backend':backend,'scope':'synthetic retrieval only; no clinical validation; no LLM', 'documents':len(docs),'queries':len(queries),'metrics':{},'rankings':[]}
    for q, row in zip(queries,scores):
        ranked=[docs[i]['id'] for i in np.argsort(-row,kind='stable')]
        output['rankings'].append({'query_id':q['id'],'ranked':ranked,'relevant':q['relevant']})
    for k in (1,3):
        values=[metrics(r['ranked'],r['relevant'],k) for r in output['rankings']]
        output['metrics'][str(k)]={f'Recall@{k}':float(np.mean([v['recall'] for v in values])),f'Precision@{k}':float(np.mean([v['precision'] for v in values])),f'MRR@{k}':float(np.mean([v['rr'] for v in values]))}
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['tfidf','sentence-transformer'],default='tfidf')
    parser.add_argument('--model-path')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=evaluate(args.backend,args.model_path)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text+'\n')
    print(text)
