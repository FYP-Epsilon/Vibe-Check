from sentence_transformers import SentenceTransformer, util
import torch

# Global model instance (lazy loaded)
_MODEL = None

def _get_model():
    global _MODEL
    if _MODEL is None:
        # Load a lightweight transformer model for business process semantics
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _MODEL

def compute_max_similarity(action_name: str, bpmn_tasks: list[str]) -> tuple[float, str]:
    """
    Computes cosine similarity between action_name and all bpmn_tasks.
    Returns (max_score, best_match_task).
    """
    model = _get_model()
    
    # Encode action and tasks
    action_emb = model.encode(action_name, convert_to_tensor=True)
    task_embs = model.encode(bpmn_tasks, convert_to_tensor=True)
    
    # Compute cosine similarities
    cosine_scores = util.cos_sim(action_emb, task_embs)[0]
    
    # Find the best match
    max_score, best_idx = torch.max(cosine_scores, dim=0)
    
    return float(max_score), bpmn_tasks[int(best_idx)]
