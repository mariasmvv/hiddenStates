using UnityEngine;

/// <summary>
/// Manages the 5 town level GameObjects.
/// Called by GameManager at the start of each level.
///
/// IMPORTANT:
///   Town level advances on a TIME schedule (every 5 minutes)
///   NOT based on gold. Gold is cosmetic only.
///
/// SETUP:
///   1. Create empty GameObject called "TownLevelManager"
///   2. Attach this script
///   3. In Inspector assign each town level parent GameObject:
///      townLevels[0] = TownLevel_1 (ruins)
///      townLevels[1] = TownLevel_2 (foundations)
///      townLevels[2] = TownLevel_3 (buildings)
///      townLevels[3] = TownLevel_4 (almost complete)
///      townLevels[4] = TownLevel_5 (fully rebuilt)
/// </summary>
public class TownLevelManager : MonoBehaviour
{
    // ─────────────────────────────────────────
    //  Inspector
    // ─────────────────────────────────────────
    [Header("Town Level GameObjects (assign in order 1-5)")]
    public GameObject[] townLevels = new GameObject[5];

    // ─────────────────────────────────────────
    //  Runtime
    // ─────────────────────────────────────────
    [Header("Runtime (read-only)")]
    [SerializeField] private int currentLevel = 1;

    // ─────────────────────────────────────────
    //  Unity Lifecycle
    // ─────────────────────────────────────────
    void Start()
    {
        for (int i = 0; i < townLevels.Length; i++)
            if (townLevels[i] == null)
                Debug.LogWarning($"[TownLevelManager] townLevels[{i}] not assigned!");

        SetLevel(1);
    }

    // ─────────────────────────────────────────
    //  Public API
    // ─────────────────────────────────────────

    /// <summary>
    /// Activates the town level GameObject for the given level
    /// and deactivates all others. Level is 1-based (1 through 5).
    /// </summary>
    public void SetLevel(int level)
    {
        level = Mathf.Clamp(level, 1, townLevels.Length);

        for (int i = 0; i < townLevels.Length; i++)
        {
            if (townLevels[i] == null) continue;
            townLevels[i].SetActive(i == level - 1);
        }

        currentLevel = level;
        Debug.Log($"[TownLevelManager] Town set to level {level}");
    }

    public int CurrentLevel => currentLevel;
}