"""Index only manifest-reviewed public protocols; no downloads or import side effects."""
from api import rag_service

def main():
    total=0
    for item in rag_service.manifest():
        path=rag_service.PROTOCOLS/item['name']
        content=path.read_bytes()
        approved=rag_service.reviewed(content)
        total+=rag_service.index_reviewed(content,approved)
    print(f'Indexación completa: {total} fragmentos revisados.')

if __name__=='__main__':
    from fastapi import HTTPException
    try:
        main()
    except HTTPException as exc:
        print(exc.detail)
        raise SystemExit(1)
