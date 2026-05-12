class ReactionAnnotationMixin:
    def get_reactions_count(self, obj) -> int:
        """
        Gets the count of reactions for the given object. If the provided
        object does not have a "reactions_count" attribute, this method
        returns 0.

        :param obj: The object for which the reactions count is queried.
        :type obj: Any
        :return: The number of reactions associated with the object.
        :rtype: int
        """
        return getattr(obj, "reactions_count", 0) or 0

    def get_reactions_breakdown(self, obj) -> dict[str, int]:
        """
        Provides a breakdown of various reaction counts for a given object.

        Given an object, this function retrieves the count of reactions for predefined
        types such as 'like', 'heart', 'haha', 'wow', 'sad', 'angry', and 'excited'.
        The function ensures that if a specific reaction type is missing from the object,
        the count defaults to zero.

        :param obj: The object from which the reaction counts are extracted.
        :type obj: Any
        :return: A dictionary containing reaction counts for each type of reaction.
        :rtype: Dict[str, int]
        """
        return {
            "like": getattr(obj, "reactions_like", 0) or 0,
            "heart": getattr(obj, "reactions_heart", 0) or 0,
            "haha": getattr(obj, "reactions_haha", 0) or 0,
            "wow": getattr(obj, "reactions_wow", 0) or 0,
            "sad": getattr(obj, "reactions_sad", 0) or 0,
            "angry": getattr(obj, "reactions_angry", 0) or 0,
            "excited": getattr(obj, "reactions_excited", 0) or 0,
        }

    def get_user_reaction(self, obj) -> str | None:
        return getattr(obj, "user_reaction", None)
