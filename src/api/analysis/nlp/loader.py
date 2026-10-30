from typing import Optional, Union, overload

from src.api.analysis.nlp.spacy_engine import SpacyEngine
from src.api.analysis.nlp.transformers_engine import NLPEngine, TransformersEngine


@overload
def load_nlp_engine(config_dict: None = None) -> SpacyEngine: ...


@overload
def load_nlp_engine(config_dict: dict) -> NLPEngine: ...


def load_nlp_engine(
    config_dict: Optional[dict] = None,
) -> Union[SpacyEngine, TransformersEngine]:
    """Load the NLP engine based on the provided configuration.

    Args:
        config_dict (dict, optional): model and supplier config. Defaults to None.

    Raises:
        ValueError: if the engine type is unknown.

    Returns:
        Union[SpacyEngine, TransformersEngine]: the loaded NLP engine.
    """
    if config_dict is None:
        # Default to SpaCy
        return SpacyEngine()

    engine_type = config_dict.get("nlp_engine", "spacy")
    model_name = config_dict.get("model_name", "nl_core_news_md")

    if engine_type == "spacy":
        return SpacyEngine(model_name)
    elif engine_type == "transformers":
        return TransformersEngine(model_name)
    else:
        raise ValueError(f"Onbekende NLP engine: {engine_type}")
