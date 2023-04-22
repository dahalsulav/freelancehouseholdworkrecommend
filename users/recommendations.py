from math import sqrt
from users.models import Worker
from tasks.models import Task


def pearson_correlation(user1_ratings, user2_ratings):
    """
    Calculate the Pearson Correlation coefficient between two users.
    """
    # Find the common items that both users have rated
    common_items = set(user1_ratings.keys()).intersection(set(user2_ratings.keys()))

    # If there are no common items, return 0
    if not common_items:
        return 0

    # Calculate the means of each user's ratings
    user1_mean = sum(user1_ratings[item] for item in common_items) / len(common_items)
    user2_mean = sum(user2_ratings[item] for item in common_items) / len(common_items)

    # Calculate the numerator and denominators for the Pearson Correlation coefficient
    numerator = sum(
        (user1_ratings[item] - user1_mean) * (user2_ratings[item] - user2_mean)
        for item in common_items
    )
    denominator = sqrt(
        sum((user1_ratings[item] - user1_mean) ** 2 for item in common_items)
        * sum((user2_ratings[item] - user2_mean) ** 2 for item in common_items)
    )

    # If the denominator is zero, return 0
    if denominator == 0:
        return 0

    # Calculate the Pearson Correlation coefficient and return it
    return numerator / denominator


def get_worker_recommendations(customer_ratings):
    """
    Get recommended workers for a customer based on their ratings.
    """
    # Create a dictionary to store the worker recommendations and their similarity scores
    recommendations = {}

    # Loop over all workers
    for worker in Worker.objects.all():
        # Get all the ratings for the current worker
        worker_ratings = {}
        for task in Task.objects.filter(worker=worker, rating__isnull=False):
            worker_ratings[task.customer.id] = task.rating

        # Calculate the similarity score between the customer's ratings and the worker's ratings
        similarity_score = pearson_correlation(customer_ratings, worker_ratings)

        # Add the worker and their similarity score to the recommendations dictionary
        if similarity_score > 0:
            recommendations[worker.id] = similarity_score

    # Sort the recommendations dictionary by similarity score in descending order
    sorted_recommendations = sorted(
        recommendations.items(), key=lambda x: x[1], reverse=True
    )

    # Return the sorted recommendations
    return sorted_recommendations
