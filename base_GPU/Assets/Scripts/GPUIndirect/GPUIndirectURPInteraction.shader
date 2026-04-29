Shader "Custom/GPUIndirectURPInteraction"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (1,1,1,1)
        _HoverColor ("Hover Color", Color) = (1,0.85,0.2,1)
        _ZoneColor ("Zone Color", Color) = (0.35,0.85,1,1)
        _HoveredInstance ("Hovered Instance", Int) = -1
    }

    SubShader
    {
        Tags
        {
            "RenderType"="Opaque"
            "Queue"="Geometry"
            "RenderPipeline"="UniversalPipeline"
        }

        Pass
        {
            Name "ForwardLit"

            HLSLPROGRAM

            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5

            // Required for RenderMeshIndirect
            #define UNITY_INDIRECT_DRAW_ARGS IndirectDrawIndexedArgs
            #include "UnityIndirect.cginc"

            // URP includes
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct GPUIndirectMovement
            {
                float4 position_scale;
                int nodeRandomInt;
                float nodeRandomFloat;
                float2 nodePadding;
            };

            StructuredBuffer<GPUIndirectMovement> _InstanceDataBuffer;

            float4 _BaseColor;
            float4 _HoverColor;
            float4 _ZoneColor;
            float4 _ZoneMin;
            float4 _ZoneMax;
            int _HoveredInstance;

            struct Attributes
            {
                float3 positionOS : POSITION;
                float3 normalOS : NORMAL;
                uint vertexID : SV_VertexID;
                uint instanceID : SV_InstanceID;
            };

            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
                nointerpolation uint instanceIndex : TEXCOORD0;
                float3 worldPosition : TEXCOORD1;
                nointerpolation bool isInZone : TEXCOORD2;
            };

            // Quaternion rotation helper
            float3 RotateVector(float3 v, float4 q)
            {
                return v + 2.0 * cross(q.xyz, cross(q.xyz, v) + q.w * v);
            }

            bool IsInsideZone(float3 worldPosition)
            {
                return worldPosition.x >= _ZoneMin.x && worldPosition.x <= _ZoneMax.x &&
                       worldPosition.z >= _ZoneMin.z && worldPosition.z <= _ZoneMax.z;
            }

            Varyings vert(Attributes IN)
            {
                Varyings OUT;

                // Required for indirect rendering
                InitIndirectDrawArgs(0);

                uint instanceIndex = GetIndirectInstanceID(IN.instanceID);

                GPUIndirectMovement data = _InstanceDataBuffer[instanceIndex];

                // Optional visibility toggle

                float3 pos = IN.positionOS;

                // Scale
                pos *= data.position_scale.w;

                // Unity-style Y-axis rotation
                float3x3 rotY = float3x3(
                    1, 0, 0,
                    0, 1, 0,
                    0, 0, 1
                );

                pos = mul(rotY, pos);

                // Translation
                pos += data.position_scale.xyz;
                OUT.positionHCS = TransformWorldToHClip(pos);
                OUT.instanceIndex = instanceIndex;
                OUT.worldPosition = pos;
                OUT.isInZone = IsInsideZone(data.position_scale.xyz);

                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                if (_HoveredInstance >= 0 && IN.instanceIndex == (uint)_HoveredInstance)
                {
                    return _HoverColor;
                }

                if (IN.isInZone)
                {
                    return _ZoneColor;
                }

                return _BaseColor;
            }

            ENDHLSL
        }
    }
}