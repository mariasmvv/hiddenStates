using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Manages transitions between town level Scenes.
/// Each scene should contain its own unique terrain and layout.
/// </summary>
public class TownLevelManager : MonoBehaviour
{
    [Header("Scene Names (Assign in order 1-5)")]
    [Tooltip("Ensure these names match exactly with scenes in Build Settings")]
    public string[] townSceneNames = new string[5];

    [Header("Runtime (read-only)")]
    [SerializeField] private int currentLevel = 1;

    void Start()
    {

    }

    /// <summary>
    /// Loads the scene for the given level.
    /// Level is 1-based (1 through 5).
    /// </summary>
    void Awake()
    {
        if (FindObjectsOfType<TownLevelManager>().Length > 1)
    {
        Destroy(gameObject);
        return;
    }
        // Ensure the scene loader survives the transition it triggers
        DontDestroyOnLoad(gameObject);
    } 
    
    public void SetLevel(int level)
    {
        level = Mathf.Clamp(level, 1, townSceneNames.Length);
        
        string sceneToLoad = townSceneNames[level - 1];

        if (!string.IsNullOrEmpty(sceneToLoad))
        {
            currentLevel = level;
            Debug.Log($"[TownLevelManager] Loading Scene: {sceneToLoad}");
            
            // This will unload the current scene and load the new one
            SceneManager.LoadScene(sceneToLoad, LoadSceneMode.Single);
        }
        else
        {
            Debug.LogError($"[TownLevelManager] Scene name at index {level - 1} is empty!");
        }
    }

    public int CurrentLevel => currentLevel;
}