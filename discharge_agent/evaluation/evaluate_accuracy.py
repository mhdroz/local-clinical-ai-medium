from discharge_agent.evaluation.evaluation_utils import (
    normalize_gold_proc,
    scalar_scores,
    f1_list,
    SCALAR_FIELDS,
    agg_mean,
)
import pandas as pd


def run_evaluation(data, gold_consensus):
    scalar_rows = []
    list_rows = []

    for note_idx, (note_preds, gold_note_raw) in enumerate(zip(data, gold_consensus)):
        gold_note = normalize_gold_proc(gold_note_raw)
        for model, pred in note_preds.items():
            s = scalar_scores(pred, gold_note)
            s["model"] = model
            s["note_idx"] = note_idx
            scalar_rows.append(s)

            labs_pred = pred.get("most_recent_labs", []) or []
            labs_gold = gold_note.get("most_recent_labs", []) or []
            meds_pred = (pred.get("medication_changes", {}) or {}).get(
                "new_medications", []
            ) or []
            meds_gold = (gold_note.get("medication_changes", {}) or {}).get(
                "new_medications", []
            ) or []
            fup_pred = pred.get("follow_up_appointments", []) or []
            fup_gold = gold_note.get("follow_up_appointments", []) or []
            proc_pred = pred.get("procedures_performed", []) or []
            proc_gold = gold_note.get("procedures_performed", []) or []

            tp_l, fp_l, fn_l, p_l, r_l, f1_l = f1_list(labs_pred, labs_gold, "labs")
            tp_m, fp_m, fn_m, p_m, r_m, f1_m = f1_list(meds_pred, meds_gold, "meds")
            tp_f, fp_f, fn_f, p_f, r_f, f1_f = f1_list(fup_pred, fup_gold, "followups")
            tp_p, fp_p, fn_p, p_p, r_p, f1_p = f1_list(
                proc_pred, proc_gold, "procedures"
            )

            # Micro across lists (TP/FP/FN summed)
            TP = tp_l + tp_m + tp_f + tp_p
            FP = fp_l + fp_m + fp_f + fp_p
            FN = fn_l + fn_m + fn_f + fn_p
            p_all = TP / (TP + FP) if (TP + FP) > 0 else 0.0
            r_all = TP / (TP + FN) if (TP + FN) > 0 else 0.0
            f1_all = 2 * p_all * r_all / (p_all + r_all) if (p_all + r_all) > 0 else 0.0

            list_rows.append(
                {
                    "model": model,
                    "note_idx": note_idx,
                    "labs_p": p_l,
                    "labs_r": r_l,
                    "labs_f1": f1_l,
                    "meds_p": p_m,
                    "meds_r": r_m,
                    "meds_f1": f1_m,
                    "followups_p": p_f,
                    "followups_r": r_f,
                    "followups_f1": f1_f,
                    "procedures_p": p_p,
                    "procedures_r": r_p,
                    "procedures_f1": f1_p,
                    "all_lists_p": p_all,
                    "all_lists_r": r_all,
                    "all_lists_f1": f1_all,
                }
            )

    df_scalar = pd.DataFrame(scalar_rows)
    df_lists = pd.DataFrame(list_rows)

    scalar_cols = (
        [f"{f}_exact" for f in SCALAR_FIELDS]
        + [f"{f}_soft" for f in SCALAR_FIELDS]
        + ["scalar_exact_acc", "scalar_soft_acc"]
    )
    list_cols = [
        "labs_p",
        "labs_r",
        "labs_f1",
        "meds_p",
        "meds_r",
        "meds_f1",
        "followups_p",
        "followups_r",
        "followups_f1",
        "procedures_p",
        "procedures_r",
        "procedures_f1",
        "all_lists_p",
        "all_lists_r",
        "all_lists_f1",
    ]
    agg_scalar = agg_mean(df_scalar, scalar_cols)
    agg_lists = agg_mean(df_lists, list_cols)
    summary = agg_scalar.merge(agg_lists, on="model", how="outer").sort_values(
        "all_lists_f1", ascending=False
    )

    return summary
