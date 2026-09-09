using UnityEngine;

/// <summary>Implemented by components that can start a Wireshark/tshark capture with a given filter and output filename.</summary>
public interface IWiresharkTracking
{
    public void StartTracking(string filter, string filename);
}
