from rag.evaluation.evaluate import metrics, evaluate

def test_rank_metrics_known_cases():
    assert metrics(['wrong','right'],{'right'},2)=={'recall':1.0,'precision':0.5,'rr':0.5}
    assert metrics(['wrong'],{'right'},3)=={'recall':0,'precision':0,'rr':0}
    assert metrics(['a','a','b'],{'a','b'},3)=={'recall':1,'precision':2/3,'rr':1}

def test_retrieval_fixture_reproducible():
    result=evaluate()
    assert result==evaluate()
    assert result['queries']==6
    for values in result['metrics'].values():
        assert all(0 <= value <= 1 for value in values.values())
