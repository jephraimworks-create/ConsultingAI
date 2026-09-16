"""Small, local, explainable feedback model.

The model is intentionally not trained after every click. A user explicitly
starts retraining after enough confirmed Yes/No calls have accumulated.
"""
from __future__ import annotations
import os
from pathlib import Path
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from .database import db

MODEL_PATH=Path(os.getenv("MENSANA_MODEL","models/opportunity_model.joblib"))
FEATURES=("revenue_growth","margin_change","expense_growth","recent_acquisition","restructuring","management_change","efficiency_mentions","cost_mentions","financial_score","operational_score","transformation_score","nlp_score","fit_score")

def train():
    """Train when at least 10 labels and both classes exist; return clear status."""
    with db() as con:
        rows=con.execute(f"""SELECT {','.join('f.'+x for x in FEATURES)},c.opportunity FROM calls c JOIN features f ON f.company_id=c.company_id WHERE c.opportunity IN ('YES','NO') AND c.voided_at IS NULL""").fetchall()
    positives=sum(r["opportunity"]=="YES" for r in rows)
    if len(rows)<10 or positives==0 or positives==len(rows):
        return {"accepted":False,"message":"Need at least 10 confirmed Yes/No calls, including both outcomes.","labels":len(rows)}
    X=np.array([[float(r[x] or 0) for x in FEATURES] for r in rows]); y=np.array([1 if r["opportunity"]=="YES" else 0 for r in rows])
    stratify=y if min(np.bincount(y))>=2 else None
    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=.25,random_state=42,stratify=stratify)
    model=Pipeline([("scale",StandardScaler()),("classifier",LogisticRegression(class_weight="balanced",random_state=42,max_iter=1000))])
    model.fit(X_train,y_train); accuracy=float(accuracy_score(y_test,model.predict(X_test)))
    MODEL_PATH.parent.mkdir(parents=True,exist_ok=True); joblib.dump({"model":model,"features":FEATURES},MODEL_PATH)
    with db() as con:
        con.execute("INSERT INTO model_runs(label_count,positive_count,accuracy,accepted,notes) VALUES(?,?,?,?,?)",(len(rows),positives,accuracy,1,"Local logistic regression"))
        candidates=con.execute(f"SELECT company_id,{','.join(FEATURES)} FROM features").fetchall()
        for row in candidates:
            vector=np.array([[float(row[x] or 0) for x in FEATURES]])
            probability=float(model.predict_proba(vector)[0,1])
            heuristic=con.execute("SELECT heuristic_score FROM features WHERE company_id=?",(row["company_id"],)).fetchone()[0]
            # Blend learned feedback with the transparent score so early models cannot dominate.
            final=round(.6*float(heuristic)+.4*(probability*100),1)
            con.execute("UPDATE features SET model_probability=?,final_score=? WHERE company_id=?",(probability,final,row["company_id"]))
    return {"accepted":True,"accuracy":round(accuracy,3),"labels":len(rows),"positives":positives}

def status():
    with db() as con:
        run=con.execute("SELECT * FROM model_runs ORDER BY id DESC LIMIT 1").fetchone()
        labels=con.execute("SELECT COUNT(*) FROM calls WHERE opportunity IN ('YES','NO') AND voided_at IS NULL").fetchone()[0]
    return {"model_exists":MODEL_PATH.exists(),"new_label_count":labels-(run["label_count"] if run else 0),"last_run":dict(run) if run else None}
