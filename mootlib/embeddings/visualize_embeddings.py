import pandas as pd
import plotly.express as px
from umap import UMAP


def reduce_dimensions(embeddings_df, n_components=2):
    """Reduce dimensionality of embeddings using UMAP."""
    umap = UMAP(n_components=n_components, random_state=42)
    return umap.fit_transform(embeddings_df)


def create_visualization(df_to_viz):
    """Create an interactive plotly visualization of the embeddings."""
    # Reduce dimensions
    reduced_embeddings = reduce_dimensions(
        df_to_viz.drop(
            [
                "source_platform",
                "question",
                "closest_questions_text",
                "closest_questions",
                "formatted_outcomes",
            ],
            axis=1,
        ),
    )

    # Create visualization DataFrame
    viz_df = pd.DataFrame(reduced_embeddings, columns=["x", "y"])
    viz_df["source_platform"] = df_to_viz["source_platform"]

    # Add question text and closest questions
    viz_df["question"] = df_to_viz["question"]
    viz_df["closest_questions"] = df_to_viz["closest_questions"]
    viz_df["formatted_outcomes"] = df_to_viz["formatted_outcomes"]
    viz_df["closest_questions_formatted"] = viz_df["closest_questions"].apply(
        lambda x: "<br>".join([f"• {q}" for q in x]),
    )

    # Create the plot
    fig = px.scatter(
        viz_df,
        x="x",
        y="y",
        color="source_platform",
        color_discrete_map={
            "Metaculus": "red",
            "Polymarket": "gray",
            "GJOpen": "blue",
            "PredictIt": "lightgreen",
            "Manifold": "orange",
        },
        hover_data=[
            "question",
            "source_platform",
            "formatted_outcomes",
            "closest_questions_formatted",
        ],
        title="UMAP Visualization of Question Embeddings",
        labels={"x": "TSNE Component 1", "y": "TSNE Component 2"},
    )

    # Customize hover template
    fig.update_traces(
        hovertemplate="Question: %{customdata[0]} (%{customdata[1]})<br>Outcomes:"
        " %{customdata[2]}<br>Closest Questions:<br>%{customdata[3]}<br><br>"
        "<extra></extra>",
    )

    # Update layout
    fig.update_layout(
        hovermode="closest",
        showlegend=True,
        legend_title_text="Source",
        width=1000,
        height=1000,
    )

    return fig


if __name__ == "__main__":
    # Load the data
    meta_questions_df = pd.read_csv("questions_df.csv", index_col=0)
    meta_embeddings_df = pd.read_csv("meta_embeddings.csv", index_col=0)
    poly_embeddings_df = pd.read_csv("poly_embeddings.csv", index_col=0)

    # Create and show the visualization
    fig = create_visualization(
        meta_embeddings_df,
        poly_embeddings_df,
        meta_questions_df,
    )
    fig.show()
