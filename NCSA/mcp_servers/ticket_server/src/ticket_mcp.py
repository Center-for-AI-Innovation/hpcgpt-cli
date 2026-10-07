from __future__ import annotations

import logging

from fastmcp import FastMCP

from src.config import TicketMCPConfig
from src.store import TicketStore

log = logging.getLogger("TICKET_MCP_SERVER")


class TicketMCP(FastMCP):
    """
    HPC-GPT Ticket Knowledge Base MCP Server.
    Exposes the deduplicated/clustered support-ticket Q&A knowledge base, backed
    by an in-memory SQLite FTS5 index with bm25 ranking.
    """

    def __init__(self, name: str, config: TicketMCPConfig):
        super().__init__(name)
        self.config = config
        self.store = TicketStore(config.resolve_source(), db_path=config.db_path)

        self.add_tool(self.search_tickets)
        self.add_tool(self.get_ticket)
        self.add_tool(self.list_clusters)
        self.add_tool(self.get_cluster)
        self.add_tool(self.stats)
        log.info("Initialized Ticket MCP Server with config: %s", self.config)

    def search_tickets(self, query: str, limit: int = 10, cluster: str = "") -> list[dict]:
        """
        MCP Tool: search_tickets
        Description: Search the ticket Q&A knowledge base with FTS5/bm25 ranking.
        Parameters:
            - query: free-text query
            - limit: max results to return (default 10)
            - cluster: optional cluster/topic to restrict the search to
        Returns:
            - A list of {custom_id, cluster, snippet, score}, highest score first.
        """
        return self.store.search(query, limit, cluster)

    def get_ticket(self, custom_id: str) -> dict:
        """
        MCP Tool: get_ticket
        Description: Fetch a single ticket's full question and answer by id.
        Parameters:
            - custom_id: the ticket id (e.g. SUP-21267)
        Returns:
            - The ticket's question, answer, cluster and raw record.
        """
        return self.store.get(custom_id)

    def list_clusters(self) -> list[dict]:
        """
        MCP Tool: list_clusters
        Description: List the clusters/topics and how many Q&A pairs each holds.
        Returns:
            - A list of {cluster, count}, largest first.
        """
        return self.store.list_clusters()

    def get_cluster(self, cluster: str, limit: int = 20) -> list[dict]:
        """
        MCP Tool: get_cluster
        Description: Return the Q&A pairs belonging to a cluster/topic.
        Parameters:
            - cluster: cluster/topic name (case-insensitive)
            - limit: max pairs to return (default 20)
        Returns:
            - A list of {custom_id, question, answer, cluster}.
        """
        return self.store.get_cluster(cluster, limit)

    def stats(self) -> dict:
        """
        MCP Tool: stats
        Description: Summary of the loaded knowledge base.
        Returns:
            - {backend, total_pairs, clusters, source}.
        """
        return self.store.stats()