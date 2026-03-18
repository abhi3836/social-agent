"""Twitter Publisher — post drafted content to Twitter/X via Tweepy."""

import logging
import re

import tweepy

from config import AgentConfig

logger = logging.getLogger("social-agent")


class TwitterPublisher:
    """Posts single tweets or threads to Twitter using the v2 API."""

    def __init__(self, config: AgentConfig):
        if not all(
            [
                config.twitter_api_key,
                config.twitter_api_secret,
                config.twitter_access_token,
                config.twitter_access_token_secret,
            ]
        ):
            raise ValueError(
                "Twitter posting requires TWITTER_API_KEY, TWITTER_API_SECRET, "
                "TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_TOKEN_SECRET to be set."
            )
        self.client = tweepy.Client(
            consumer_key=config.twitter_api_key,
            consumer_secret=config.twitter_api_secret,
            access_token=config.twitter_access_token,
            access_token_secret=config.twitter_access_token_secret,
        )

    def post(self, draft_content: str) -> list[str]:
        """Parse draft content and post as tweet or thread. Returns list of tweet IDs."""
        tweets = self._parse_tweets(draft_content)
        if not tweets:
            logger.warning("No tweet content found in draft — skipping post.")
            return []

        tweet_ids = []
        reply_to_id = None

        for tweet in tweets:
            if reply_to_id:
                response = self.client.create_tweet(
                    text=tweet,
                    in_reply_to_tweet_id=reply_to_id,
                )
            else:
                response = self.client.create_tweet(text=tweet)

            tweet_id = str(response.data["id"])
            tweet_ids.append(tweet_id)
            reply_to_id = tweet_id
            logger.info(f"Posted tweet id={tweet_id}: {tweet[:60]}...")

        logger.info(f"Twitter: posted {len(tweet_ids)} tweet(s).")
        return tweet_ids

    @staticmethod
    def _parse_tweets(content: str) -> list[str]:
        """Extract tweet text from the structured draft format.

        Handles both single-tweet drafts and threads (## Tweet N headers).
        Strips markdown headers, image suggestion lines, and type annotations.
        """
        # Remove header block up to first ---
        content = re.sub(r"^#.*?\n.*?\n\n---\n", "", content, flags=re.DOTALL)
        # Remove trailing image suggestion and separator
        content = re.sub(r"\n---\n\*\*Image suggestion:\*\*.*$", "", content, flags=re.DOTALL)
        content = content.strip()

        # Thread: split on ## Tweet N markers
        thread_parts = re.split(r"##\s*Tweet\s*\d+\s*\n", content)
        tweets = [t.strip() for t in thread_parts if t.strip()]

        # If only one part, it's a single tweet — return as-is
        return tweets
