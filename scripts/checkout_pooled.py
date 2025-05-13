# %%

from pathlib import Path

import numpy as np
import pandas as pd
from embedding_utils import (
    create_visualization,
    embed_questions_df,
    get_closest_questions,
    get_distance_matrix,
)
from sklearn.manifold import TSNE

df_file = Path("/Users/vigji/code/vigjibot/data/combined_markets.csv")
pooled_df = pd.read_csv(df_file)
pooled_df = pooled_df.drop_duplicates(subset=["question"])

# %%
# %%
pooled_df.head()
gj_df = pooled_df[pooled_df.source_platform == "GJOpen"]
len(gj_df), len(gj_df.question.unique())
# %%
# ================================================
# Embed questions
# ================================================

embedded_df = embed_questions_df(pooled_df, question_column="question")
embedded_df["question"] = pooled_df["question"]
embedded_df["source_platform"] = pooled_df["source_platform"]
embedded_df["formatted_outcomes"] = pooled_df["formatted_outcomes"]
embedded_df = embedded_df.reset_index(drop=True)
embedded_df.head()


distance_matrix = get_distance_matrix(embedded_df)

# Create and show the visualization
embedded_df["closest_questions"] = embedded_df.apply(
    lambda row: get_closest_questions(row, distance_matrix, embedded_df, n_closest=20),
    axis=1,
)
embedded_df["closest_questions_text"] = embedded_df["closest_questions"].apply(
    lambda x: "\n".join(
        [f"{q}  {a} ({source}; {distance})" for q, a, source, distance in x],
    ),
)
embedded_df.head()

for i in (0, 2, *np.random.Generator.integers(0, len(embedded_df), 10)):
    example = embedded_df.iloc[i]


def reduce_dimensions(
    embeddings_data: np.ndarray | pd.DataFrame, n_components: int = 2
) -> np.ndarray:
    """Reduce dimensionality of embeddings using UMAP."""
    tsne = TSNE(n_components=n_components, random_state=42)
    return tsne.fit_transform(embeddings_data)


# %%
create_visualization(embedded_df)
# %%
# %%
