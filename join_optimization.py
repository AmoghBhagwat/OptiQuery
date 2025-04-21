from graphviz import Digraph
import uuid
from parse import RANode, Relation, Selection, Projection, Join, Subquery, COLOR_MAP
import re
import sqlglot
from sqlglot import parse_one, expressions as exp
from itertools import permutations

def extract_tables(condition: str):
    """Roughly extract identifiers like sq.a, t1.b from condition."""
    tokens = condition.replace('=', ' ').replace('<', ' ').replace('>', ' ').replace('<=', ' ').replace('>=', ' ').split()
    tables = []
    for token in tokens:
        if '.' in token:
            # token should not be a a constant
            if not re.match(r'^\d+(\.\d+)?$', token):
                tables.append(token.strip().split('.')[0])
    return tables

temp_root = 0

def _find_joins(node: RANode, edges: list[tuple[str,str,str]], alias_to_RANode: dict[str,RANode], join_obtained: int, parent: RANode):
    if join_obtained == 0:
        if isinstance(node,Join):
            if node.condition.upper() != "TRUE":
                global temp_root

                temp_root = parent
                join_obtained = 1
            else:
                _find_joins(node.left, edges, alias_to_RANode, join_obtained, node)            
        else:
            child = getattr(node, 'child', None)
            if child:
                _find_joins(child, edges, alias_to_RANode, join_obtained, node)
    
    if join_obtained == 1:
        edge = extract_tables(node.condition)
        edges.append((edge[0],edge[1],node.condition))
        
        if(isinstance(node.left,Join)):
            _find_joins(node.left, edges, alias_to_RANode, join_obtained, node)
        else:
            alias_to_RANode[node.left.alias] = node.left
            
        if(isinstance(node.right,Join)): 
            _find_joins(node.right, edges, alias_to_RANode, join_obtained, node)
        else:
            alias_to_RANode[node.right.alias] = node.right

def join_optimize(node: RANode) -> RANode:
    # cost should be computed for RANode
    edges = []
    alias_to_RANode = dict()
    _find_joins(node, edges, alias_to_RANode, 0, node)
    n = len(edges)+1
    if n < 2:
        return node
    
    best_perm = []
    best_cost = float('inf')
    
    for perm in permutations(edges):
        valid = True
        visited = set()
        curr_cost = max(50,alias_to_RANode[perm[0][0]].cost * alias_to_RANode[perm[0][0]].cost* 0.01)
        cumulative_cost = curr_cost
        visited.add(perm[0][0])
        visited.add(perm[0][1])
        
        for edge in perm[1:]:
            if edge[0] in visited:
                visited.add(edge[1])
                curr_cost = max(50,curr_cost * alias_to_RANode[edge[1]].cost * 0.01)
                cumulative_cost+=curr_cost
            elif edge[1] in visited:
                visited.add(edge[0])
                curr_cost = max(50,curr_cost * alias_to_RANode[edge[0]].cost * 0.01)
                cumulative_cost+=curr_cost
            else:
                valid = False
                break
        
        if not valid:
            continue
        
        if(cumulative_cost<best_cost):
            best_perm = [edge for edge in perm]
            best_cost = cumulative_cost
    
    curr = Join(alias_to_RANode[best_perm[0][0]], alias_to_RANode[best_perm[0][1]], best_perm[0][2])
    visited = set()
    visited.add(best_perm[0][0])
    visited.add(best_perm[0][1])
    for edge in best_perm[1:]:
        if edge[0] in visited:
            visited.add(edge[1])
            curr = Join(curr, alias_to_RANode[edge[1]], edge[2])
        else:
            visited.add(edge[0])
            curr = Join(curr, alias_to_RANode[edge[0]], edge[2])
    
    temp_root.child = curr
    return node
    
    
            
        
        
            
        
        
                    
        
    
