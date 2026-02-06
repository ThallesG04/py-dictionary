from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional, List


@dataclass
class _Node:
    key: Any
    key_hash: int
    value: Any


# Sentinela para marcação de item removido (tombstone).
# Mesmo que você não implemente __delitem__, isso ajuda a manter o probing correto.
_TOMBSTONE = object()


class Dictionary:
    """
    Implementação de dicionário (hash table) usando:
    - tabela como lista (array) de nós
    - tratamento de colisões por linear probing (open addressing)
    """

    def __init__(self, capacity: int = 8, load_factor: float = 0.75) -> None:
        if capacity < 1:
            capacity = 8

        # Para simplificar o probing, é comum trabalhar com capacidade potência de 2,
        # mas aqui não é obrigatório. Ainda assim, garantimos pelo menos 8.
        self._capacity: int = max(8, capacity)
        self._load_factor: float = load_factor

        # Quantidade de pares chave-valor realmente armazenados (não conta tombstone)
        self._size: int = 0

        # Tabela: cada posição pode ser:
        # - None (vazio)
        # - _Node (ocupado)
        # - _TOMBSTONE (ocupado no passado, removido)
        self._table: List[Optional[object]] = [None] * self._capacity

    def __len__(self) -> int:
        return self._size

    def _should_resize(self) -> bool:
        # Quando passar do load factor, redimensiona
        return (self._size + 1) / self._capacity >= self._load_factor

    def _index(self, key_hash: int) -> int:
        # Índice inicial na tabela
        return key_hash % self._capacity

    def _find_slot(self, key: Any, key_hash: int) -> int:
        """
        Encontra o índice onde a chave está OU onde deve ser inserida.
        - Se a chave existir: retorna o índice dela
        - Se não existir: retorna o melhor índice disponível (None ou tombstone)
        """
        start: int = self._index(key_hash)
        first_tombstone: Optional[int] = None

        i: int = start
        while True:
            cell = self._table[i]

            if cell is None:
                # Se encontramos uma célula vazia, podemos inserir aqui.
                # Mas se vimos tombstone antes, preferimos reutilizar ele.
                return first_tombstone if first_tombstone is not None else i

            if cell is _TOMBSTONE:
                # Guardamos o primeiro tombstone encontrado para possível inserção.
                if first_tombstone is None:
                    first_tombstone = i

            else:
                # Aqui cell é _Node
                node: _Node = cell  # type: ignore[assignment]
                if node.key_hash == key_hash and node.key == key:
                    return i

            # Linear probing: avança (com wrap-around)
            i = (i + 1) % self._capacity

            # Segurança: se der uma volta completa, a tabela está cheia (não deveria acontecer
            # porque fazemos resize antes, mas deixamos para evitar loop infinito).
            if i == start:
                # Se existir tombstone, pelo menos conseguimos inserir
                if first_tombstone is not None:
                    return first_tombstone
                raise RuntimeError("Hashtable cheia. Resize falhou ou não foi executado.")

    def __setitem__(self, key: Any, value: Any) -> None:
        """
        Adiciona ou atualiza um par chave-valor.
        """
        if self._should_resize():
            self._resize()

        key_hash: int = hash(key)
        slot: int = self._find_slot(key, key_hash)

        cell = self._table[slot]
        if cell is None or cell is _TOMBSTONE:
            # Inserção nova
            self._table[slot] = _Node(key=key, key_hash=key_hash, value=value)
            self._size += 1
        else:
            # Atualização (chave já existia)
            node: _Node = cell  # type: ignore[assignment]
            node.value = value

    def __getitem__(self, key: Any) -> Any:
        """
        Recupera o valor associado à chave. Se não existir, levanta KeyError.
        """
        key_hash: int = hash(key)
        slot: int = self._find_slot(key, key_hash)

        cell = self._table[slot]
        if isinstance(cell, _Node):
            return cell.value

        # Se caiu em None/Tombstone, significa que a chave não existe
        raise KeyError(key)

    def _resize(self) -> None:
        """
        Dobra a capacidade e reinsere os elementos (rehash).
        """
        old_table: List[Optional[object]] = self._table

        self._capacity *= 2
        self._table = [None] * self._capacity
        self._size = 0

        for cell in old_table:
            if isinstance(cell, _Node):
                # Reinsere usando nosso __setitem__ (rehash com nova capacidade)
                self[cell.key] = cell.value
